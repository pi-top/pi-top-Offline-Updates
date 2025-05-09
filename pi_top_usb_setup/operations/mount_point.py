import logging
from pathlib import Path
from typing import Callable, Optional

from pi_top_usb_setup.exceptions import ExtractionError, NotEnoughSpaceException
from pi_top_usb_setup.file_structure import MountPointStructure
from pi_top_usb_setup.utils import (
    drive_has_enough_free_space,
    extract_file,
    get_tar_gz_extracted_size,
    umount_usb_drive,
)

logger = logging.getLogger(__name__)


class MountPointOperations:
    def __init__(self, structure: MountPointStructure) -> None:
        self.structure = structure

    def extract_setup_file(
        self, destination: Path, on_progress: Optional[Callable] = None
    ) -> None:
        """Extracts the newest compressed setup bundle found in the mount point"""
        files = self.structure.find_setup_files()
        if len(files) >= 1:
            logger.info(f"Found {len(files)} setup files; will use '{files[0]}'...")
            self._do_extract_setup_file(files[0], destination, on_progress)
        else:
            logger.warning(
                f"No compressed setup file found in '{self.structure.mount_point}'; skipping extraction"
            )

    def _do_extract_setup_file(
        self, filename: Path, destination: Path, on_progress: Optional[Callable] = None
    ) -> None:
        """Extracts the given filename into a temporary folder"""
        if not filename.exists():
            logger.warning(f"File '{filename}' doesn't exist; skipping extraction")
            return

        # Get extracted size of the tar.gz file
        try:
            space = get_tar_gz_extracted_size(str(filename))
        except Exception as e:
            raise ExtractionError(f"Error getting extracted size of '{filename}', {e}")

        # Check if there's enough free space in the SD card
        drive = "/"
        if not drive_has_enough_free_space(drive=drive, space=space):
            raise NotEnoughSpaceException(
                f"Not enough space to extract '{filename}' into {drive}"
            )

        try:
            extract_file(
                file=str(filename),
                destination=str(destination),
                on_progress=on_progress,
            )
            logger.info(f"File {filename} extracted into {destination}")
        except Exception as e:
            raise ExtractionError(f"Error extracting '{filename}': {e}")

    def umount_usb_drive(self) -> None:
        """Umounts the USB drive"""
        if self.usb_drive_is_present:
            umount_usb_drive(self.structure.mount_point)
        else:
            logger.info("No USB drive to umount, skipping ...")

    @property
    def usb_drive_is_present(self) -> bool:
        return self.structure.is_usb_drive()
