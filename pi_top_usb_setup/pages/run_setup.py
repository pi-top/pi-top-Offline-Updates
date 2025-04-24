import logging
import os
from enum import Enum
from threading import Thread
from typing import Callable

from pt_miniscreen.components.mixins import HasGutterIcons
from pt_miniscreen.components.progress_bar import ProgressBar
from pt_miniscreen.core.component import Component
from pt_miniscreen.core.components import Text
from pt_miniscreen.core.utils import apply_layers, layer

from pi_top_usb_setup.app_fs import AppFilesystem
from pi_top_usb_setup.exceptions import (
    ExtractionError,
    NotAnAptRepository,
    NotEnoughSpaceException,
)
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


# Use enum value to represent 'starting' progress %
class RunStates(Enum):
    ERROR = -1
    INIT = 0
    EXTRACTING_TAR = 5
    UPDATING_SYSTEM = 25
    CONFIGURING_DEVICE = 80
    INSTALLING_CERTIFICATES = 82
    COPYING_FILES = 85
    COMPLETING_ONBOARDING = 90
    RUNNING_SCRIPTS = 95
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
            },
            **kwargs,
        )

        try:
            self.fs = AppFilesystem(mount_point=os.environ["PT_USB_SETUP_MOUNT_POINT"])
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
            # Extract compressed file
            self._extract_file()

            # Umount USB drive
            self.fs.umount_usb_drive()

            # Update packages
            self._update_system()

            # Configure device: process json file
            self._configure_device()

            # Copy certficates over to the device
            self._install_certificates()

            # Copy files over to the device
            self._copy_files_to_device()

            # Run scripts
            self._run_scripts()

            # Finish onboarding if necessary
            self._complete_onboarding()

            self.state.update({"run_state": RunStates.DONE})
        except RestartingSystemdService:
            logger.warning("Restarting systemd service, exiting ...")
            return
        except Exception as e:
            logger.error(f"{e}")

        if callable(self.on_complete):
            message = "Device setup is complete! Press any button to exit."
            if self.fs.requires_reboot:
                message = (
                    "Device setup is complete! Press any button to reboot the device!"
                )
            elif self.state.get("run_state") == RunStates.ERROR:
                message = f"There was an error during setup: E{self.state.get('error').value}. Press any button to exit."
                if self.state.get("error") == AppErrors.NOT_ENOUGH_SPACE:
                    message = "There's not enough free space in your pi-top to continue. Press any button to exit"
            self.on_complete(
                {"message": message, "requires_reboot": self.fs.requires_reboot}
            )

    def _extract_file(self):
        self.state.update({"run_state": RunStates.EXTRACTING_TAR})
        try:
            self.fs.extract_setup_file(
                on_progress=lambda percentage: self.state.update(
                    {"tar_progress": percentage}
                )
            )
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

    def _update_system(self):
        if os.environ.get("PT_USB_SETUP_SKIP_UPDATE", "0") == "1":
            logger.info("Skipping system update; script called with --skip-update")
            return

        try:
            updater = SystemUpdater(
                apt_repository=self.fs.UPDATES_FOLDER,
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
                    mount_point=self.fs.SETUP_FOLDER
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
        self.state.update({"run_state": RunStates.CONFIGURING_DEVICE})
        try:
            self.fs.configure_device(
                on_progress=lambda percentage: self.state.update(
                    {"config_progress": percentage}
                ),
            )
        except Exception as e:
            self.state.update(
                {"run_state": RunStates.ERROR, "error": AppErrors.CONFIGURATION_ERROR}
            )
            raise Exception(f"Config Error: {e}")

    def _install_certificates(self):
        self.state.update({"run_state": RunStates.INSTALLING_CERTIFICATES})
        try:
            self.fs.install_certificates(
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
        self.state.update({"run_state": RunStates.COPYING_FILES})
        try:
            self.fs.copy_files(
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
        self.state.update({"run_state": RunStates.COMPLETING_ONBOARDING})
        try:
            self.fs.complete_onboarding(
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
        self.state.update({"run_state": RunStates.RUNNING_SCRIPTS})
        try:
            self.fs.run_scripts(
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

        return value

    def _text(self):
        run_state = self.state.get("run_state")
        # If the USB device is still connected ...
        if run_state == RunStates.UPDATING_SYSTEM and self.fs.usb_drive_is_present:
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
