import json
import logging
from os import listdir, makedirs, path, walk
from shutil import copy2, rmtree
from typing import Callable, Dict, Optional

from pitop.common.command_runner import run_command
from pt_os_web_portal.backend.helpers.finalise import (
    deprioritise_openbox_session,
    disable_ap_mode,
    enable_firmware_updater_service,
    enable_further_link_service,
    enable_pt_miniscreen,
    onboarding_completed,
    restore_files,
    stop_first_boot_app_autostart,
    update_eeprom,
)
from pt_os_web_portal.backend.helpers.keyboard import set_keyboard_layout
from pt_os_web_portal.backend.helpers.language import set_locale
from pt_os_web_portal.backend.helpers.registration import set_registration_email
from pt_os_web_portal.backend.helpers.timezone import set_timezone
from pt_os_web_portal.backend.helpers.wifi_country import set_wifi_country

from pi_top_usb_setup.file_structure import UsbSetupStructure
from pi_top_usb_setup.network import Network
from pi_top_usb_setup.utils import print_folder_recursively

logger = logging.getLogger(__name__)


class CoreOperations:
    def __init__(self, fs: UsbSetupStructure) -> None:
        self.fs = fs

        self.requires_reboot = False
        self.config: Dict = {}

    def read_config_file(self) -> None:
        """Reads the configuration JSON file from the setup bundle into a dictionary"""
        logger.info(f"Reading configuration file from {self.fs.json_file()} ...")
        config_file_path = self.fs.json_file()
        if not config_file_path.exists():
            logger.info(
                f"No device configuration file found in '{config_file_path}'; skipping...."
            )
            return

        with open(str(config_file_path)) as file:
            content = file.read()
            config = json.loads(content)

        self.config = config

    def configure_device(self, on_progress: Optional[Callable] = None) -> None:
        """Configures the device based on the configuration file"""
        logger.info("Configuring device...")

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
                function(args)
                if callable(on_progress):
                    on_progress(float(100.0 * i / len(lookup)))
            except Exception as e:
                logger.error(f"{e}")

    def set_network(self, on_progress: Optional[Callable] = None) -> None:
        """Sets the network based on the configuration file"""
        logger.info("Setting network...")

        network_data = self.config.get("network")
        if network_data is None:
            logger.info("No network data found in configuration file, skipping...")
            return

        logger.info(f"Network data: {network_data}")

        try:
            Network.from_dict(network_data).connect()
        except Exception as e:
            logger.error(f"Error setting network: {e}")

        if callable(on_progress):
            on_progress(100.0)

    def install_certificates(self, on_progress: Optional[Callable] = None) -> None:
        """Installs the certificates from the setup bundle into the device"""
        logger.info("Installing certificates...")

        certificates_folder_path = self.fs.certificates_folder()
        if not certificates_folder_path.exists():
            logger.info("No certificates to install; skipping...")
            return

        try:
            print_folder_recursively(str(certificates_folder_path))
        except Exception as e:
            logger.error(f"Error listing files in {certificates_folder_path}: {e}")

        for index, (key, data) in enumerate(self.fs.CERTIFICATE_PATHS.items()):
            dst = data["path"]
            progress_factor = int((index / len(self.fs.CERTIFICATE_PATHS)))

            folder = f"{certificates_folder_path}/{key}"
            if not path.isdir(folder):
                continue

            # Create destination directory if it doesn't exist
            makedirs(dst, exist_ok=True)

            files_copied = 0
            files = listdir(folder)
            total_files = len(files)

            # Copy files to destination directory
            for file in files:
                path_to_file = f"{folder}/{file}"
                if not path.isfile(path_to_file):
                    continue
                logger.info(f"Copying certificate {file} into {dst} ...")
                copy2(path_to_file, dst)
                files_copied += 1
                if on_progress:
                    progress = int(
                        (1 + files_copied / total_files) * progress_factor * 100
                    )
                    on_progress(progress)

            command = data.get("command")
            if files_copied > 0 and command:
                logger.info(f"Running command '{command}' ...")
                run_command(command, timeout=60)

    def copy_files(self, on_progress: Optional[Callable] = None) -> None:
        """Copies the files from the files directory of the setup bundle into the device"""
        logger.info("Copying files...")

        files_folder_path = self.fs.files_folder()
        if not files_folder_path.exists():
            logger.info("No files to copy; skipping...")
            return

        try:
            print_folder_recursively(str(files_folder_path))
        except Exception as e:
            logger.error(f"Error listing files in {files_folder_path}: {e}")

        total_files = sum(len(files) for _, _, files in walk(str(files_folder_path)))
        files_copied = 0

        for root, dirs, files in walk(str(files_folder_path)):
            for file in files:
                source_path = path.join(root, file)

                # Get the relative path from the source_dir
                relative_path = path.relpath(source_path, str(files_folder_path))

                # Destination path based on root
                destination_path = path.join("/", relative_path)

                # Create target directory if it doesn't exist
                makedirs(path.dirname(destination_path), exist_ok=True)

                # Copy file
                copy2(source_path, destination_path)
                logger.info(f"Copied file {source_path} to {destination_path}")

                # Update progress
                files_copied += 1
                if on_progress:
                    progress = int((files_copied / total_files) * 100)
                    on_progress(progress)

    def run_scripts(self, on_progress: Optional[Callable] = None) -> None:
        """Runs the scripts from the scripts directory of the setup bundle"""
        logger.info("Running scripts...")
        scripts_folder_path = self.fs.scripts_folder()
        if not scripts_folder_path.exists():
            logger.info("No scripts to run; skipping...")
            return

        try:
            print_folder_recursively(str(scripts_folder_path))
        except Exception as e:
            logger.error(f"Error listing files in {scripts_folder_path}: {e}")

        logger.info(f"Running scripts from {scripts_folder_path}")

        filenames = sorted(listdir(scripts_folder_path))
        for i, file in enumerate(filenames):
            f = path.join(scripts_folder_path, file)
            if path.exists(f):
                logger.info(f"Making script executable: {file} ...")
                run_command(f"chmod +x {f}", timeout=10)
                logger.info(f"Executing script: {file} ...")
                run_command(f, timeout=600)
                if callable(on_progress):
                    on_progress(float(100.0 * i / len(filenames)))

        if callable(on_progress):
            on_progress(100.0)

    def complete_onboarding(self, on_progress: Optional[Callable] = None) -> None:
        """Completes the onboarding process for the device"""
        logger.info("Completing onboarding for device ...")
        if onboarding_completed():
            logger.info("Device already onboarded; skipping ...")
            return

        functions = (
            enable_firmware_updater_service,
            enable_further_link_service,
            deprioritise_openbox_session,
            restore_files,
            stop_first_boot_app_autostart,
            update_eeprom,
            enable_pt_miniscreen,
            disable_ap_mode,
        )

        for i, func in enumerate(functions):
            try:
                logger.info(f"Executing {func} ...")
                func()
            except Exception as e:
                logger.error(f"{e}")

            if callable(on_progress):
                on_progress(float(100.0 * i / len(functions)))

        self.requires_reboot = True

    def cleanup(self) -> None:
        """Cleans up the device after the setup is complete"""
        try:
            logger.info(f"Cleaning up {self.fs.directory} ...")
            rmtree(self.fs.directory)
        except Exception as e:
            logger.error(f"Error cleaning up {self.fs.directory}: {e}")
