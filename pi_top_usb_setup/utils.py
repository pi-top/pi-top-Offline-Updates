import logging
import shutil
import tarfile
from signal import SIGTERM, raise_signal
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


def close_app() -> None:
    # TODO: umount
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
    with tarfile.open(file, "r:gz") as tar:
        tar.extractall(path=destination)


def drive_has_enough_free_space(drive: str, space: int) -> bool:
    _, _, free_space = shutil.disk_usage(drive)
    logger.info(f"Drive in {drive} has {free_space} free space")
    return space < free_space


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
