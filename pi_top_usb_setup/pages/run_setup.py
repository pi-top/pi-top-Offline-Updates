import logging
import os
from enum import Enum
from pathlib import Path
from tempfile import mkdtemp
from threading import Thread
from typing import Callable

from pitop.common.state_manager import StateManager
from pt_miniscreen.components.mixins import HasGutterIcons
from pt_miniscreen.components.progress_bar import ProgressBar
from pt_miniscreen.core.component import Component
from pt_miniscreen.core.components import Text
from pt_miniscreen.core.utils import apply_layers, layer

from pi_top_usb_setup.exceptions import (
    ExtractionError,
    NotAnAptRepository,
    NotEnoughSpaceException,
)
from pi_top_usb_setup.file_structure import MountPointStructure, UsbSetupStructure
from pi_top_usb_setup.operations import CoreOperations, MountPointOperations
from pi_top_usb_setup.system_updater import SystemUpdater
from pi_top_usb_setup.utils import (
    RestartingSystemdService,
    get_package_version,
    restart_service_and_skip_user_confirmation_dialog,
)

logger = logging.getLogger(__name__)


FONT_SIZE = 10


class TextWithDots:
    """Returns the provided text followed by a set of max 3 dots; the number of dots
    changes each time the text is printed, providing a sense of animation.
    The length of the printed string is always the same so that it's position on the miniscreen doesn't change.
    """

    def __init__(self, text):
        self.base = text
        self.dots = "..."

    def __repr__(self):
        dots = self.dots.strip()
        if len(dots) == 3:
            dots = "."
        else:
            dots += "."
        # Fill with spaces if necessary
        self.dots = dots + (3 - len(dots)) * " "
        return f"{self.base} {self.dots}"


class ConfigFileKeys(Enum):
    INSTALL_UPDATE = "install_update"
    INSTALL_CERTIFICATES = "install_certificates"
    COPY_FILES = "copy_files"
    RUN_SCRIPTS = "run_scripts"
    INSTALL_NETWORK = "install_network"
    COMPLETE_ONBOARDING = "complete_onboarding"
    CONFIGURE_DEVICE = "configure_device"


# Use enum value to represent 'starting' progress %
class RunStates(Enum):
    ERROR = -1
    INIT = 0
    EXTRACTING_TAR = 5
    UPDATING_SYSTEM = 25
    CONFIGURING_DEVICE = 80
    INSTALLING_CERTIFICATES = 82
    CONFIGURING_NETWORK = 83
    COPYING_FILES = 85
    RUNNING_SCRIPTS = 90
    COMPLETING_ONBOARDING = 95
    DONE = 100


class AppErrors(Enum):
    NONE = 0
    NOT_ENOUGH_SPACE = 1
    UPDATE_ERROR = 2
    EXTRACTION = 3
    CONFIGURATION_ERROR = 4
    ONBOARDING_ERROR = 5
    COPY_ERROR = 6
    SCRIPTS_ERROR = 7
    CERTIFICATE_INSTALLATION_ERROR = 8
    NETWORK_CONFIGURATION_ERROR = 9


class RunSetupPage(Component, HasGutterIcons):
    def __init__(self, on_complete: Callable, **kwargs):
        self.on_complete = on_complete
        super().__init__(
            initial_state={
                "run_state": RunStates.INIT,
                "error": AppErrors.NONE,
                "apt_progress": 0,
                "tar_progress": 0,
                "config_progress": 0,
                "onboarding_progress": 0,
                "scripts_progress": 0,
                "certificate_progress": 0,
                "network_progress": 0,
                "copy_progress": 0,
            },
            **kwargs,
        )

        self.state_manager = None
        try:
            self.state_manager = StateManager("pi-top-usb-setup")
        except Exception as e:
            logger.error(f"Couldn't create state manager: {e}")

        try:
            folder = os.environ["PT_USB_SETUP_MOUNT_POINT"]

            self.mount_point = MountPointStructure(folder)

            # If the files are not extracted yet, we'll create a temporary directory
            # and extract the setup file there later...
            if not UsbSetupStructure.is_valid_directory(folder):
                folder = mkdtemp()
            self.extracted_fs = UsbSetupStructure(folder)

            self.core_operations = CoreOperations(self.extracted_fs)
            self.mount_point_operations = MountPointOperations(self.mount_point)
        except Exception as e:
            logger.error(f"{e}")
            raise e

        self._wait_text = TextWithDots("Please wait")
        self.text_component = self.create_child(
            Text,
            text=self._text(),
            get_text=self._text,
            font_size=FONT_SIZE,
            align="center",
            vertical_align="center",
            wrap=True,
        )
        self.progress_bar = self.create_child(
            ProgressBar, progress=self._current_progress
        )

        Thread(target=self.run_setup, daemon=True).start()

    def run_setup(self):
        try:
            # Extract compressed file if necessary
            self._extract_file()

            # Read the JSON file
            self.core_operations.read_config_file()

            # Update packages
            self._update_system()

            # Configure device: process json file
            self._configure_device()

            # Copy certficates over to the device
            self._install_certificates()

            # Configure network
            self._set_network()

            # Copy files over to the device
            self._copy_files_to_device()

            # Run scripts
            self._run_scripts()

            # Finish onboarding if necessary
            self._complete_onboarding()

            self.state.update({"run_state": RunStates.DONE})

            self.core_operations.cleanup()
        except RestartingSystemdService:
            logger.warning("Restarting systemd service, exiting ...")
            return
        except Exception as e:
            logger.error(f"{e}")

        if callable(self.on_complete):
            message = "Device setup is complete! Press any button to exit."
            if self.core_operations.requires_reboot:
                message = (
                    "Device setup is complete! Press any button to reboot the device!"
                )
            elif self.state.get("run_state") == RunStates.ERROR:
                message = f"There was an error during setup: E{self.state.get('error').value}. Press any button to exit."
                if self.state.get("error") == AppErrors.NOT_ENOUGH_SPACE:
                    message = "There's not enough free space in your pi-top to continue. Press any button to exit"
            self.on_complete(
                {
                    "message": message,
                    "requires_reboot": self.core_operations.requires_reboot,
                }
            )

    def _extract_file(self):
        self.state.update({"run_state": RunStates.EXTRACTING_TAR})
        try:
            self.mount_point_operations.extract_setup_file(
                destination=Path(self.extracted_fs.directory),
                on_progress=lambda percentage: self.state.update(
                    {"tar_progress": percentage}
                ),
            )
            # Umount USB drive
            self.mount_point_operations.umount_usb_drive()
        except NotEnoughSpaceException:
            self.state.update(
                {"run_state": RunStates.ERROR, "error": AppErrors.NOT_ENOUGH_SPACE}
            )
            raise
        except ExtractionError:
            self.state.update(
                {"run_state": RunStates.ERROR, "error": AppErrors.EXTRACTION}
            )
            raise

    def _should_run(self, stage: ConfigFileKeys) -> bool:
        should_run = False
        try:
            should_run = isinstance(
                self.state_manager, StateManager
            ) and self.state_manager.get("app", stage.value, "false") in (
                "true",
                "1",
            )
        except Exception as e:
            logger.error(f"Error getting state manager: {e}")
        return should_run

    def _update_system(self):
        if not self._should_run(ConfigFileKeys.INSTALL_UPDATE):
            logger.warning("Skipping system update due to system configuration...")
            return

        try:
            updater = SystemUpdater(
                apt_repository=str(self.extracted_fs.updates_folder()),
                on_progress=lambda percentage: self.state.update(
                    {"apt_progress": percentage}
                ),
                on_error=lambda message: logger.error(f"{message}"),
            )

            version_before_update = get_package_version("pi-top-usb-setup")
            logger.info(
                f"Before update, 'pi-top-usb-setup' version is {version_before_update}"
            )

            logger.info("Starting system update")
            self.state.update({"run_state": RunStates.UPDATING_SYSTEM})

            # Update sources
            updater.update()

            # Upgrade pi-top-usb-setup package first
            updater.upgrade_package("pi-top-usb-setup")

            # Restart service if it was updated
            version_after_update = get_package_version("pi-top-usb-setup")
            if version_before_update != version_after_update:
                logger.warning(
                    f"Package 'pi-top-usb-setup' was updated from '{version_before_update}' to '{version_after_update}', restarting app..."
                )
                restart_service_and_skip_user_confirmation_dialog(
                    mount_point=str(self.extracted_fs.folder())
                )
                raise RestartingSystemdService

            # Upgrade system
            updater.upgrade()
            logger.info("Finished updating")
        except RestartingSystemdService:
            raise
        except NotAnAptRepository as e:
            logger.warning(f"{e}")
            return
        except Exception as e:
            self.state.update(
                {"run_state": RunStates.ERROR, "error": AppErrors.UPDATE_ERROR}
            )
            raise Exception(f"Update Error: {e}")

    def _configure_device(self):
        if not self._should_run(ConfigFileKeys.CONFIGURE_DEVICE):
            logger.warning(
                "Skipping device configuration due to system configuration..."
            )
            return

        self.state.update({"run_state": RunStates.CONFIGURING_DEVICE})
        try:
            self.core_operations.configure_device(
                on_progress=lambda percentage: self.state.update(
                    {"config_progress": percentage}
                ),
            )
        except Exception as e:
            self.state.update(
                {"run_state": RunStates.ERROR, "error": AppErrors.CONFIGURATION_ERROR}
            )
            raise Exception(f"Config Error: {e}")

    def _set_network(self):
        if not self._should_run(ConfigFileKeys.INSTALL_NETWORK):
            logger.warning(
                "Skipping network configuration due to system configuration..."
            )
            return

        self.state.update({"run_state": RunStates.CONFIGURING_NETWORK})
        try:
            self.extracted_fs.set_network(
                on_progress=lambda percentage: self.state.update(
                    {"network_progress": percentage}
                ),
            )
        except Exception:
            self.state.update(
                {
                    "run_state": RunStates.ERROR,
                    "error": AppErrors.NETWORK_CONFIGURATION_ERROR,
                }
            )

    def _install_certificates(self):
        if not self._should_run(ConfigFileKeys.INSTALL_CERTIFICATES):
            logger.warning(
                "Skipping certificate installation due to system configuration..."
            )
            return

        self.state.update({"run_state": RunStates.INSTALLING_CERTIFICATES})
        try:
            self.core_operations.install_certificates(
                on_progress=lambda percentage: self.state.update(
                    {"certificate_progress": percentage}
                ),
            )
        except Exception as e:
            self.state.update(
                {
                    "run_state": RunStates.ERROR,
                    "error": AppErrors.CERTIFICATE_INSTALLATION_ERROR,
                }
            )
            raise Exception(f"Certificate Installation Error: {e}")

    def _copy_files_to_device(self):
        if not self._should_run(ConfigFileKeys.COPY_FILES):
            logger.warning("Skipping files copy due to system configuration...")
            return

        self.state.update({"run_state": RunStates.COPYING_FILES})
        try:
            self.core_operations.copy_files(
                on_progress=lambda percentage: self.state.update(
                    {"copy_progress": percentage}
                ),
            )
        except Exception as e:
            self.state.update(
                {"run_state": RunStates.ERROR, "error": AppErrors.COPY_ERROR}
            )
            raise Exception(f"Copy Error: {e}")

    def _complete_onboarding(self):
        if not self._should_run(ConfigFileKeys.COMPLETE_ONBOARDING):
            logger.warning("Skipping onboarding due to system configuration...")
            return

        self.state.update({"run_state": RunStates.COMPLETING_ONBOARDING})
        try:
            self.core_operations.complete_onboarding(
                on_progress=lambda percentage: self.state.update(
                    {"onboarding_progress": percentage}
                ),
            )
        except Exception as e:
            self.state.update(
                {"run_state": RunStates.ERROR, "error": AppErrors.ONBOARDING_ERROR}
            )
            raise Exception(f"Onboarding Error: {e}")

    def _run_scripts(self):
        if not self._should_run(ConfigFileKeys.RUN_SCRIPTS):
            logger.warning("Skipping scripts run due to system configuration...")
            return

        self.state.update({"run_state": RunStates.RUNNING_SCRIPTS})
        try:
            self.core_operations.run_scripts(
                on_progress=lambda percentage: self.state.update(
                    {"scripts_progress": percentage}
                ),
            )
        except Exception as e:
            self.state.update(
                {"run_state": RunStates.ERROR, "error": AppErrors.SCRIPTS_ERROR}
            )
            raise Exception(f"Scripts Error: {e}")

    def _current_progress(self):
        state = self.state.get("run_state")
        value = state.value

        if state is RunStates.EXTRACTING_TAR:
            # Include tar extraction progress
            value += (
                self.state.get("tar_progress", 0)
                / 100
                * (RunStates.UPDATING_SYSTEM.value - value)
            )
        elif state is RunStates.UPDATING_SYSTEM:
            # Include apt progress
            value += (
                self.state.get("apt_progress", 0)
                / 100
                * (RunStates.CONFIGURING_DEVICE.value - value)
            )
        elif state is RunStates.CONFIGURING_DEVICE:
            value += (
                self.state.get("config_progress", 0)
                / 100
                * (RunStates.INSTALLING_CERTIFICATES.value - value)
            )
        elif state is RunStates.INSTALLING_CERTIFICATES:
            value += (
                self.state.get("certificate_progress", 0)
                / 100
                * (RunStates.CONFIGURING_NETWORK.value - value)
            )
        elif state is RunStates.CONFIGURING_NETWORK:
            value += (
                self.state.get("network_progress", 0)
                / 100
                * (RunStates.COPYING_FILES.value - value)
            )
        elif state is RunStates.COPYING_FILES:
            value += (
                self.state.get("copy_progress", 0)
                / 100
                * (RunStates.RUNNING_SCRIPTS.value - value)
            )
        elif state is RunStates.RUNNING_SCRIPTS:
            value += (
                self.state.get("scripts_progress", 0)
                / 100
                * (RunStates.COMPLETING_ONBOARDING.value - value)
            )
        elif state is RunStates.COMPLETING_ONBOARDING:
            value += (
                self.state.get("onboarding_progress", 0)
                / 100
                * (RunStates.DONE.value - value)
            )
        elif state is RunStates.DONE:
            value += (
                self.state.get("onboarding_progress", 0)
                / 100
                * (RunStates.DONE.value - value)
            )

        return value

    def _text(self):
        run_state = self.state.get("run_state")
        # If the USB device is still connected ...
        if (
            run_state == RunStates.UPDATING_SYSTEM
            and self.mount_point_operations.usb_drive_is_present
        ):
            return "You can remove the USB drive; setup process will continue"

        return str(self._wait_text)

    def render(self, image):
        offset = 5

        vertical_split = 40
        progress_bar_size = (
            image.width - 2 * offset,
            image.height - vertical_split - 2 * offset,
        )
        return apply_layers(
            image,
            [
                layer(
                    self.text_component.render,
                    size=(image.width, image.height - progress_bar_size[1]),
                    pos=(0, 0),
                ),
                layer(
                    self.progress_bar.render,
                    size=progress_bar_size,
                    pos=(offset, vertical_split + offset),
                ),
            ],
        )

    def top_gutter_icon(self):
        return None

    def bottom_gutter_icon(self):
        return None
