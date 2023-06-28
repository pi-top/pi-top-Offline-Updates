import logging
import os
from enum import Enum
from threading import Thread

from pt_miniscreen.components.mixins import Actionable
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
    close_app,
    get_package_version,
    restart_service_and_skip_updates,
)

logger = logging.getLogger(__name__)


FONT_SIZE = 12


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
    UPDATING_SYSTEM = 10
    DONE = 100


class AppErrors(Enum):
    NONE = 0
    NOT_ENOUGH_SPACE = 1
    UPDATE_ERROR = 2
    EXTRACTION = 3


class RunSetupPage(Component, Actionable):
    def __init__(self, **kwargs):
        super().__init__(
            initial_state={
                "run_state": RunStates.INIT,
                "error": AppErrors.NONE,
                "apt_progress": 0,
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

            # Try to update packages
            self._update_system()

            self.state.update({"run_state": RunStates.DONE})
        except Exception as e:
            logger.error(f"{e}")

    def _extract_file(self):
        self.state.update({"run_state": RunStates.EXTRACTING_TAR})
        try:
            self.fs.extract_setup_file()
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
            logger.info("Starting system update")
            self.state.update({"run_state": RunStates.UPDATING_SYSTEM})
            updater.update()
            updater.upgrade()
            logger.info("Finished updating")
        except NotAnAptRepository as e:
            logger.warning(f"{e}")
            return
        except Exception as e:
            self.state.update(
                {"run_state": RunStates.ERROR, "error": AppErrors.UPDATE_ERROR}
            )
            raise Exception(f"Update Error: {e}")

        # Restart service if it was updated
        if version_before_update != get_package_version("pi-top-usb-setup"):
            logger.info("Package 'pi-top-usb-setup' was updated, restarting app...")
            restart_service_and_skip_updates()

    def _current_progress(self):
        state = self.state.get("run_state")
        value = state.value
        if state is RunStates.UPDATING_SYSTEM:
            # Include apt progress
            value += (
                self.state.get("apt_progress", 0) / 100 * (RunStates.DONE.value - value)
            )
        return value

    def _text(self):
        run_state = self.state.get("run_state")
        if run_state == RunStates.DONE:
            return "Device setup is complete; Press the select button to exit."
        elif run_state == RunStates.ERROR:
            error = self.state.get("error")
            if error == AppErrors.NOT_ENOUGH_SPACE:
                return "The pi-top doesn't have enough free space."
            return "There was an error. Press the select button to exit."

        # If the USB device is still connected ...
        if run_state == RunStates.UPDATING_SYSTEM and self.fs.usb_drive_is_present:
            return "You can remove the USB drive; setup process will continue"

        return str(self._wait_text)

    def perform_action(self):
        run_state = self.state.get("run_state")
        if run_state in (RunStates.DONE, RunStates.ERROR):
            self.fs.umount_usb_drive()
            close_app()

    def render(self, image):
        offset = 5

        if self.state.get("run_state") in (RunStates.DONE, RunStates.ERROR):
            return apply_layers(
                image,
                [
                    layer(
                        self.text_component.render,
                        size=image.size,
                        pos=(0, 0),
                    ),
                ],
            )

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
