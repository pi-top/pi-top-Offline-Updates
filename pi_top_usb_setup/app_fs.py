import logging
from pathlib import Path

from pitop.common.command_runner import run_command

from pi_top_usb_setup.exceptions import ExtractionError, NotEnoughSpaceException
from pi_top_usb_setup.utils import (
    drive_has_enough_free_space,
    extract_file,
    get_tar_gz_extracted_size,
    umount_usb_drive,
)

logger = logging.getLogger(__name__)


class AppFilesystem:
    def __init__(self, mount_point) -> None:
        self.MOUNT_POINT = mount_point
        self.USB_SETUP_FILE = f"{mount_point}/pi-top-usb-setup.tar.gz"
        self.TEMP_FOLDER = "/tmp"
        self.SETUP_FOLDER = f"{self.TEMP_FOLDER}/pi-top-usb-setup"
        self.UPDATES_FOLDER = f"{self.SETUP_FOLDER}/updates"

        if not any(
            [
                Path(self.USB_SETUP_FILE).exists(),
                Path(self.UPDATES_FOLDER).is_dir(),
            ]
        ):
            raise Exception(
                f"Files {self.USB_SETUP_FILE} or {self.UPDATES_FOLDER} not found, exiting ..."
            )

        self.device = None
        if mount_point:
            self.device = run_command(
                f"findmnt -n -o SOURCE --target {mount_point}", timeout=5
            ).strip()

    @property
    def usb_drive_is_present(self) -> bool:
        return Path(self.device).exists() if self.device else False

    def umount_usb_drive(self) -> None:
        umount_usb_drive(self.MOUNT_POINT)

    def extract_setup_file(self) -> None:
        if not Path(self.USB_SETUP_FILE).exists():
            logger.warning(
                f"File {self.USB_SETUP_FILE} doesn't exist; skipping extraction"
            )
            return

        # Check if there's enough free space in the SD card
        if not drive_has_enough_free_space(
            drive="/", space=get_tar_gz_extracted_size(self.USB_SETUP_FILE)
        ):
            raise NotEnoughSpaceException(
                f"Not enough space to extract {self.USB_SETUP_FILE} into {self.TEMP_FOLDER}"
            )

        try:
            extract_file(file=self.USB_SETUP_FILE, destination=self.TEMP_FOLDER)
            logger.info(f"File {self.USB_SETUP_FILE} extracted into {self.TEMP_FOLDER}")
        except Exception as e:
            raise ExtractionError(f"Error extracting '{self.USB_SETUP_FILE}': {e}")
