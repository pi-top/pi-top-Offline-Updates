import json
import logging
import os
from pathlib import Path
from typing import Callable, Dict, Optional

import click
import click_logging
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

from pi_top_usb_setup.network import Network
from pi_top_usb_setup.utils import boot_partition

logger = logging.getLogger()
click_logging.basic_config(logger)


class ConfigureSystem:
    def __init__(self, path: str) -> None:
        if not Path(path).exists():
            raise FileNotFoundError(
                f"Configuration file '{path}' doesn't exist; exiting ..."
            )
        self.path = path
        self.config: Dict = {}
        self.read()
        self.requires_reboot = False

    def read(self):
        with open(self.path) as file:
            content = file.read()
            self.config = json.loads(content)

    def configure(self, on_progress: Optional[Callable] = None) -> None:
        def set_network(network_data):
            logger.info(f"Setting network with data: {network_data}")
            try:
                Network.from_dict(network_data).connect()
            except Exception as e:
                logger.error(f"Error setting network: {e}")
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
            "network": set_network,
        }

        for i, (key, function) in enumerate(lookup.items()):
            if key not in self.config:
                logger.info(f"'{key}' not found in configuration file, skipping...")
                continue

            args = self.config.get(key)
            if args is None:
                logger.info(
                    f"Value for '{key}' not found in configuration file, skipping..."
                )
                continue

            try:
                logger.info(f"{key}: Executing {function} with '{args}'")
                function(self.config.get(key))
                if callable(on_progress):
                    on_progress(float(100.0 * i / len(lookup)))
            except Exception as e:
                logger.error(f"{e}")

    def onboard(
        self,
        on_progress: Optional[Callable] = None,
    ) -> None:
        if onboarding_completed():
            logger.info("Device already onboarded, skipping...")
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

    def run_all(self, on_progress: Optional[Callable] = None):
        self.configure(on_progress)
        self.onboard(on_progress)


def is_root():
    return os.geteuid() == 0


@click.command()
@click_logging.simple_verbosity_option(logger)
@click.version_option()
@click.argument("path_to_json", required=False)
def main(path_to_json) -> None:
    if not is_root():
        logger.error("This script must be run as root")
        return

    if path_to_json is None:
        path_to_json = f"{boot_partition()}/pi-top_config.json"
        logger.info(f"Using path to json: {path_to_json}")

    try:
        c = ConfigureSystem(path_to_json)
        c.run_all()

        logger.info(
            f"Configuration completed - removing configuration file {path_to_json}"
        )
        Path(path_to_json).unlink(missing_ok=True)

        if c.requires_reboot:
            logger.info("Rebooting ...")
            os.system("reboot")
    except FileNotFoundError:
        logger.info(f"Configuration file {path_to_json} not found, skipping ...")
    except Exception as e:
        logger.error(f"{e}")
