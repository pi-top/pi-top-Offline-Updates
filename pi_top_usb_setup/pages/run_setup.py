import logging
import os
from enum import Enum
from pathlib import Path
from threading import Thread

from pitop.common.command_runner import run_command
from pt_miniscreen.components.mixins import Actionable
from pt_miniscreen.components.progress_bar import ProgressBar
from pt_miniscreen.core.component import Component
from pt_miniscreen.core.components import Text
from pt_miniscreen.core.utils import apply_layers, layer

from pi_top_usb_setup.system_updater import SystemUpdater
from pi_top_usb_setup.utils import (
    AppPaths,
    close_app,
    drive_has_enough_free_space,
    extract_file,
    get_package_version,
    get_tar_gz_extracted_size,
    systemctl,
    umount_usb_drive,
)

logger = logging.getLogger(__name__)


FONT_SIZE = 14


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
            mount_point = os.environ["PT_USB_SETUP_MOUNT_POINT"]
            self.paths = AppPaths(mount_point)
            self.device = run_command(
                f"findmnt -n -o SOURCE --target {mount_point}", timeout=5
            ).strip()
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
            # Extract compressed files
            self._extract_file(
                file=self.paths.USB_SETUP_FILE, destination=self.paths.TEMP_FOLDER
            )
            self._extract_file(
                file=self.paths.UPDATES_TAR_FILE, destination=self.paths.SETUP_FOLDER
            )

            # Umount USB drive
            umount_usb_drive(self.paths.MOUNT_POINT)

            # Try to update packages
            self._update_system()

            self.state.update({"run_state": RunStates.DONE})
        except Exception as e:
            logger.error(f"{e}")

    def _extract_file(self, file: str, destination: str):
        if not Path(file).exists():
            logger.warning(f"File {file} doesn't exist; skipping extraction")
            return

        # Check if there's enough free space
        if not drive_has_enough_free_space(
            drive="/", space=get_tar_gz_extracted_size(file)
        ):
            self.state.update(
                {"run_state": RunStates.ERROR, "error": AppErrors.NOT_ENOUGH_SPACE}
            )
            raise Exception(f"Not enough space to extract {file} into {destination}")

        self.state.update({"run_state": RunStates.EXTRACTING_TAR})
        try:
            extract_file(file=file, destination=destination)
            logger.info(f"File {file} extracted; removing ...")
            os.remove(file)
        except Exception as e:
            self.state.update(
                {"run_state": RunStates.ERROR, "error": AppErrors.EXTRACTION}
            )
            raise Exception(f"Error extracting '{file}': {e}")

    def _update_system(self):
        if os.environ.get("PT_USB_SETUP_SKIP_UPDATE", "0") == "1":
            logger.info("Skipping system update; script called with --skip-update")
            return

        if not Path(self.paths.UPDATES_FOLDER).is_dir():
            logger.warning(
                f"Couldn't find {self.paths.UPDATES_FOLDER}, skipping system update"
            )
            return

        version_before_update = get_package_version("pi-top-usb-setup")
        self._run_system_update()
        version_after_update = get_package_version("pi-top-usb-setup")

        # Restart service if it was updated
        if version_before_update != version_after_update:
            self._restart_service_and_skip_updates()

    def _run_system_update(self):
        logger.info("Starting system update")

        def on_error(message):
            logger.error(f"{message}")

        def on_progress(percentage):
            self.state.update({"apt_progress": percentage})

        updater = SystemUpdater(
            apt_repository=self.paths.UPDATES_FOLDER,
            on_progress=on_progress,
            on_error=on_error,
        )
        try:
            self.state.update({"run_state": RunStates.UPDATING_SYSTEM})
            updater.update()
            updater.upgrade()
        except Exception as e:
            self.state.update(
                {"run_state": RunStates.ERROR, "error": AppErrors.UPDATE_ERROR}
            )
            raise Exception(f"Update Error: {e}")

        logger.info("Finished updating")

    def _restart_service_and_skip_updates(self):
        # Restarts service and skips dialog & updates
        logger.info("Package 'pi-top-usb-setup' was updated, restarting app...")

        # Start an instance with arguments; these should be encoded
        encoded_args = run_command(
            "systemd-escape -- '--skip-dialog --skip-update'", timeout=5
        )
        systemctl("start", f"pt-usb-setup@'{encoded_args}'")

        # Stop this instance
        systemctl("stop", "pt-usb-setup")

    def _current_progress(self):
        state = self.state.get("run_state")
        value = state.value
        if state is RunStates.UPDATING_SYSTEM:
            # Display apt progress
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
        if Path(self.device).exists():
            return "You can remove the USB drive; the setup process will continue ..."

        return str(self._wait_text)

    def perform_action(self):
        run_state = self.state.get("run_state")
        if run_state in (RunStates.DONE, RunStates.ERROR):
            umount_usb_drive(self.paths.MOUNT_POINT)
            close_app()

    def render(self, image):
        offset = 5
        if (
            self.state.get("run_state") in (RunStates.DONE, RunStates.ERROR)
            or Path(self.device).exists()
        ):
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
        return apply_layers(
            image,
            [
                layer(
                    self.text_component.render,
                    size=(image.width, FONT_SIZE),
                    pos=(0, 13),
                ),
                layer(
                    self.progress_bar.render,
                    size=(image.width - 2 * offset, 15),
                    pos=(offset, 35),
                ),
            ],
        )
