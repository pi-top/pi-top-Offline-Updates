import grp
import logging
import os
import pwd
import shutil
import signal
import stat
import tarfile
import time
from pathlib import Path
from queue import Queue
from shlex import split
from subprocess import PIPE, Popen
from threading import Thread, Timer
from time import sleep
from typing import Callable, Dict, Optional

from pitop.common.command_runner import run_command

logger = logging.getLogger(__name__)


class RestartingSystemdService(Exception):
    pass


def systemctl(command: str, name: str, timeout=10) -> Optional[str]:
    try:
        cmd = f"systemctl {command} {name}.service"
        logger.info(f"Executing '{cmd}'")
        output = run_command(
            cmd,
            timeout=timeout,
            check=False,
        )
        return output.strip(" \n")
    except Exception as e:
        logger.error(f"Error on systemctl(command={command}, name={name}): {e}")
        return None


def umount_usb_drive(mount_point: str) -> None:
    logger.info(f"Umounting USB drive at {mount_point}")

    if not Path(mount_point).exists():
        logger.warning(f"Can't umount {mount_point}: destination doesn't exist")
        return

    try:
        run_command(f"umount {mount_point}", timeout=15)
    except Exception as e:
        logger.error(f"Error unmounting {mount_point}: {e}")


def close_app() -> None:
    logger.info("Closing application")
    systemctl("stop", "'pt-usb-setup@*'")
    systemctl("stop", "pt-usb-setup")


def get_tar_gz_extracted_size(file: str) -> int:
    # Gets the size of the extracted content of a tar.gz file
    # Uncompressed size is stored in the last 4 bytes of the gzip file
    # https://stackoverflow.com/a/22348071
    size = -1
    with open(file, "rb") as f:
        f.seek(-4, 2)
        size = int.from_bytes(f.read(), "little")
    logger.info(f"Size of {file} content is {size}")
    return size


def extract_file(
    file: str, destination: str, on_progress: Optional[Callable] = None
) -> None:
    logger.info(f"Extracting {file} into {destination}")
    if not Path(file).exists():
        raise Exception(f"File {file} doesn't exist")

    os.makedirs(destination, exist_ok=True)
    with tarfile.open(file, "r:gz") as tar:
        total_items = len(tar.getmembers())
        for i, member in enumerate(tar.getmembers()):
            if callable(on_progress):
                on_progress(float(i / total_items * 100.0))
            tar.extract(member=member, path=destination)


def drive_has_enough_free_space(drive: str, space: int) -> bool:
    try:
        _, _, free_space = shutil.disk_usage(drive)
        logger.info(f"Drive in {drive} has {free_space} free space")
        return space < free_space
    except Exception as e:
        logger.error(f"Error: {e}")
        return False


def get_package_version(package: str) -> str:
    version = ""
    try:
        cmd = f"dpkg-query --show {package}"
        output = run_command(cmd, timeout=10).split()
        if len(output) > 1:
            version = output[1]
    except Exception as e:
        logger.error(f"Error while getting version of '{package}': {e}")
    finally:
        logger.info(f"Package {package} version is {version}")
        return version


class Process:
    """Runs a command allowing to handle stdout and stderr messages that it produces"""

    def __init__(
        self,
        run_command: str,
        timeout: int,
        stdout_callback: Optional[Callable] = None,
        stderr_callback: Optional[Callable] = None,
    ) -> None:
        self.run_command = run_command
        self.timeout = timeout
        self.stdout_callback = stdout_callback
        self.stderr_callback = stderr_callback
        self._process: Optional[Popen] = None
        self._log_queue: Queue = Queue()

    def run(self, environment: Optional[Dict] = None) -> int:
        """Run command and wait for it to finish"""
        logging.info(f"Executing '{self.run_command}' with timeout {self.timeout}")
        self._process = Popen(
            split(self.run_command),
            stdout=PIPE,
            stderr=PIPE,
            env=environment if environment else os.environ,
            text=True,
        )

        # Handle stream messages produced by self._process
        def queue_logs(stream_name, stream):
            for line in iter(stream.readline, ""):
                self._log_queue.put((stream_name, line))
            stream.close()

        Thread(
            target=queue_logs, args=["stdout", self._process.stdout], daemon=True
        ).start()
        Thread(
            target=queue_logs, args=["stderr", self._process.stderr], daemon=True
        ).start()

        # Logs messages produced by streams in the background
        def log():
            while self._process or not self._log_queue.empty():
                try:
                    stream, message = self._log_queue.get_nowait()
                    try:
                        if stream == "stdout" and callable(self.stdout_callback):
                            self.stdout_callback(message)
                        if stream == "stderr" and callable(self.stderr_callback):
                            self.stderr_callback(message)
                    except Exception as e:
                        logger.error(f"Process user callback: {e}")
                except Exception:
                    sleep(0.5)

        Thread(target=log, daemon=True).start()

        # Handle timeout
        def terminate(process):
            logger.warning(f"Process timed out: '{self.run_command}'; terminating")
            process.terminate()

        Timer(self.timeout, terminate, [self._process]).start()

        # Wait for process to exit/timeout and return
        exit_code = self._process.wait()
        logger.info(f"Command exited with code {exit_code}")
        self.process = None
        return exit_code


def restart_service_and_skip_user_confirmation_dialog(mount_point: str):
    # Start an instance with arguments; these should be encoded
    encoded_args = run_command(
        f"systemd-escape -- '{mount_point} --skip-dialog'", timeout=5
    )
    systemctl("start", f"pt-usb-setup@'{encoded_args}'")

    # Stop this instance
    os.kill(os.getpid(), signal.SIGINT)


def get_linux_distro():
    cmd = "grep VERSION_CODENAME /etc/os-release | cut -d'=' -f2"
    process = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdout, _ = process.communicate()
    return stdout.decode().strip()


def print_folder_recursively(path):
    for root, dirs, files in os.walk(path):
        logging.info(f"\n{root}:")
        entries = dirs + files
        for entry in entries:
            full_path = os.path.join(root, entry)
            try:
                st = os.lstat(full_path)
                mode = stat.filemode(st.st_mode)
                n_links = st.st_nlink
                uid = st.st_uid
                gid = st.st_gid
                size = st.st_size
                mtime = time.strftime("%b %d %H:%M", time.localtime(st.st_mtime))
                user = pwd.getpwuid(uid).pw_name
                group = grp.getgrgid(gid).gr_name
                logging.info(
                    f"{mode} {n_links} {user} {group} {size:>8} {mtime} {entry}"
                )
            except Exception as e:
                logging.error(f"Error reading {full_path}: {e}")
