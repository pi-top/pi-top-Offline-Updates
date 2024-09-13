import logging
from pathlib import Path
from typing import Callable, Optional

from pitop.common.command_runner import run_command

from pi_top_usb_setup.configure import ConfigureSystem
from pi_top_usb_setup.exceptions import ExtractionError, NotEnoughSpaceException
from pi_top_usb_setup.utils import (
    drive_has_enough_free_space,
    extract_file,
    get_linux_distro,
    get_tar_gz_extracted_size,
    umount_usb_drive,
)

logger = logging.getLogger(__name__)


class AppFilesystem:
    USB_SETUP_FILENAME_GLOB = "pi-top-usb-setup*.tar.gz"
    TEMP_FOLDER = "/tmp"

    def __init__(self, mount_point: str) -> None:
        self.MOUNT_POINT = mount_point
        self.USB_SETUP_FILE = f"{mount_point}/pi-top-usb-setup.tar.gz"
        self.SETUP_FOLDER = f"{self.TEMP_FOLDER}/pi-top-usb-setup"
        self.DEVICE_CONFIG = f"{self.SETUP_FOLDER}/pi-top_config.json"
        self.UPDATES_FOLDER = f"{self.SETUP_FOLDER}/updates"
        if get_linux_distro() == "bookworm":
            self.UPDATES_FOLDER = f"{self.SETUP_FOLDER}/updates_bookworm"

        if not any(
            [
                len(self._find_setup_files()) > 0,
                Path(self.UPDATES_FOLDER).is_dir(),
            ]
        ):
            raise Exception(
                f"Files '{self.MOUNT_POINT}/{self.USB_SETUP_FILENAME_GLOB}' or {self.UPDATES_FOLDER} not found, exiting ..."
            )

        self.device = None
        if mount_point:
            self.device = run_command(
                f"findmnt -n -o SOURCE --target {mount_point}", timeout=5
            ).strip()

        self.setup = ConfigureSystem(self.DEVICE_CONFIG)

    def _find_setup_files(self):
        # find all setup files in mount point that match the glob pattern, sorted by date
        return sorted(
            Path(self.MOUNT_POINT).glob(self.USB_SETUP_FILENAME_GLOB),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

    @property
    def usb_drive_is_present(self) -> bool:
        return Path(self.device).exists() if self.device else False

    def umount_usb_drive(self) -> None:
        umount_usb_drive(self.MOUNT_POINT)

    def extract_setup_file(self, on_progress: Optional[Callable] = None) -> None:
        files = self._find_setup_files()
        if len(files) >= 1:
            logger.info(f"Found {len(files)} setup files; will use '{files[0]}'...")
            self._do_extract_setup_file(files[0], on_progress)
        else:
            logger.warning("No setup file found; skipping extraction")

    def _do_extract_setup_file(
        self, filename: str, on_progress: Optional[Callable] = None
    ) -> None:
        if not Path(filename).exists():
            logger.warning(f"File '{filename}' doesn't exist; skipping extraction")
            return

        # Get extracted size of the tar.gz file
        try:
            space = get_tar_gz_extracted_size(filename)
        except Exception as e:
            raise ExtractionError(f"Error getting extracted size of '{filename}', {e}")

        # Check if there's enough free space in the SD card
        if not drive_has_enough_free_space(drive="/", space=space):
            raise NotEnoughSpaceException(
                f"Not enough space to extract '{filename}' into {self.TEMP_FOLDER}"
            )

        try:
            extract_file(
                file=filename,
                destination=self.TEMP_FOLDER,
                on_progress=on_progress,
            )
            logger.info(f"File {filename} extracted into {self.TEMP_FOLDER}")
        except Exception as e:
            raise ExtractionError(f"Error extracting '{filename}': {e}")

    def configure_device(self, on_progress: Optional[Callable] = None) -> None:
        self.setup.configure(on_progress)

    def complete_onboarding(self, on_progress: Optional[Callable] = None) -> None:
        self.setup.onboard(on_progress)

    @property
    def requires_reboot(self) -> bool:
        return self.setup.requires_reboot
