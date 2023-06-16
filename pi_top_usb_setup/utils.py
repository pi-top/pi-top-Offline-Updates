import logging
import os
import shutil
import tarfile
from pathlib import Path
from typing import Optional

from pitop.common.command_runner import run_command

logger = logging.getLogger(__name__)


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
    logger.info("Umounting USB drive at {mount_point}")

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


def extract_file(file: str, destination: str) -> None:
    logger.info(f"Extracting {file} into {destination}")
    if not Path(file).exists():
        raise Exception(f"File {file} doesn't exist")

    os.makedirs(destination, exist_ok=True)
    with tarfile.open(file, "r:gz") as tar:
        tar.extractall(path=destination)


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


class AppPaths:
    def __init__(self, mount_point) -> None:
        self.MOUNT_POINT = mount_point
        self.USB_SETUP_FILE = f"{mount_point}/pi-top-usb-setup.tar.gz"
        self.SETUP_FOLDER = f"{mount_point}/pi-top-usb-setup"
        self.UPDATES_TAR_FILE = f"{self.SETUP_FOLDER}/updates.tar.gz"
        self.UPDATES_FOLDER = f"{self.SETUP_FOLDER}/updates"

        if not any(
            [
                Path(self.USB_SETUP_FILE).exists(),
                Path(self.UPDATES_TAR_FILE).exists(),
                Path(self.UPDATES_FOLDER).is_dir(),
            ]
        ):
            raise Exception(
                f"Files {self.USB_SETUP_FILE} , {self.UPDATES_TAR_FILE} or {self.UPDATES_FOLDER} not found, exiting ..."
            )


class OfflineAptSource:
    def __init__(self, path_to_repo: str) -> None:
        self.path = path_to_repo
        self.source = "/tmp/offline-apt-source.list"
        self.source_path = Path(self.source)
        self.source_path.unlink(missing_ok=True)

    def __enter__(self):
        logger.info(f"Creating offline apt source in {self.source}")
        with open(self.source, "w") as file:
            file.write(f"deb [trusted=yes] file:{self.path} ./")
        return self.source

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.source_path.unlink(missing_ok=True)
