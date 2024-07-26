import json
import logging
from pathlib import Path
from typing import Callable, Optional

from pitop.common.command_runner import run_command
from pt_os_web_portal.backend.helpers.finalise import (
    configure_landing,
    deprioritise_openbox_session,
    disable_ap_mode,
    enable_firmware_updater_service,
    enable_further_link_service,
    enable_pt_miniscreen,
    onboarding_completed,
    restore_files,
    stop_onboarding_autostart,
    update_eeprom,
)
from pt_os_web_portal.backend.helpers.keyboard import set_keyboard_layout
from pt_os_web_portal.backend.helpers.language import set_locale
from pt_os_web_portal.backend.helpers.registration import set_registration_email
from pt_os_web_portal.backend.helpers.timezone import set_timezone
from pt_os_web_portal.backend.helpers.wifi_country import set_wifi_country

from pi_top_usb_setup.exceptions import ExtractionError, NotEnoughSpaceException
from pi_top_usb_setup.utils import (
    drive_has_enough_free_space,
    extract_file,
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

        if not any(
            [
                len(self._find_setup_files()) > 0,
                Path(self.UPDATES_FOLDER).is_dir(),
            ]
        ):
            raise Exception(
                f"Files '{self.MOUNT_POINT}/{self.USB_SETUP_FILENAME_GLOB}' or {self.UPDATES_FOLDER} not found, exiting ..."
            )

        self.requires_reboot = False
        self.device = None
        if mount_point:
            self.device = run_command(
                f"findmnt -n -o SOURCE --target {mount_point}", timeout=5
            ).strip()

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
        if not Path(self.DEVICE_CONFIG).exists():
            logger.info("No device configuration file found; skipping....")
            return

        # setting the keyboard layout requires a layout and a variant
        lookup = {
            "language": set_locale,
            "country": set_wifi_country,
            "time_zone": set_timezone,
            "keyboard_layout": lambda layout_and_variant_arr: set_keyboard_layout(
                *layout_and_variant_arr
            ),
            "email": set_registration_email,
        }

        logger.info(f"Configuring device using {self.DEVICE_CONFIG}")
        with open(self.DEVICE_CONFIG) as file:
            content = file.read()
            config = json.loads(content)

        for i, (key, function) in enumerate(lookup.items()):
            if key not in config:
                logger.info(f"'{key}' not found in configuration file, skipping...")
                continue

            args = config.get(key)
            if args is None:
                logger.info(
                    f"Value for '{key}' not found in configuration file, skipping..."
                )
                continue

            try:
                logger.info(f"{key}: Executing {function} with '{args}'")
                function(config.get(key))
                if callable(on_progress):
                    on_progress(float(100.0 * i / len(lookup)))
            except Exception as e:
                logger.error(f"{e}")

    def complete_onboarding(self, on_progress: Optional[Callable] = None) -> None:
        if onboarding_completed():
            logger.info("Device already onboarded")
            return

        functions = (
            enable_firmware_updater_service,
            enable_further_link_service,
            deprioritise_openbox_session,
            restore_files,
            configure_landing,
            stop_onboarding_autostart,
            update_eeprom,
            enable_pt_miniscreen,
            disable_ap_mode,
        )

        logger.info("Completing onboarding for device ...")
        for i, func in enumerate(functions):
            try:
                logger.info(f"Executing {func} ...")
                func()
            except Exception as e:
                logger.error(f"{e}")

            if callable(on_progress):
                on_progress(float(100.0 * i / len(functions)))

        self.requires_reboot = True
