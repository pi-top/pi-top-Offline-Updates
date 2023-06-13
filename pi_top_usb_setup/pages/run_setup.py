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

from pi_top_usb_setup.common import (
    MOUNT_POINT,
    OFFLINE_APT_SOURCE,
    UPDATES_FOLDER,
    USB_SETUP_FILE,
)
from pi_top_usb_setup.utils import (
    close_app,
    drive_has_enough_free_space,
    extract_file,
    get_package_version,
    get_tar_gz_extracted_size,
)

logger = logging.getLogger(__name__)


FONT_SIZE = 14


class RunStates(Enum):
    ERROR = -1
    INIT = 0
    EXTRACTING_TAR = 1
    UPDATING_SOURCES = 2
    INSTALLING_UPDATES = 3
    DONE = 4


class AppErrors(Enum):
    NONE = 0
    NOT_ENOUGH_SPACE = 1
    UPDATE_ERROR = 2
    EXTRACTION = 3


class RunSetupPage(Component, Actionable):
    def __init__(self, **kwargs):
        super().__init__(
            initial_state={"run_state": RunStates.INIT, "error": AppErrors.NONE},
            **kwargs,
        )

        self.text_component = self.create_child(
            Text,
            text=self._text(),
            get_text=self._text,
            font_size=FONT_SIZE,
            align="center",
            vertical_align="center",
            wrap=False,
        )
        self.progress_bar = self.create_child(
            ProgressBar, progress=self._current_progress
        )

        Thread(target=self.run_setup, daemon=True).start()

    def _text(self):
        run_state = self.state.get("run_state")
        if run_state == RunStates.DONE:
            return "Device setup\nis complete;\nPress the select\nbutton to exit ..."
        elif run_state == RunStates.ERROR:
            error = self.state.get("error")
            if error == AppErrors.NOT_ENOUGH_SPACE:
                return "USB drive doesn't\nhave enough free\nspace"
            return "There was an error,\n please try again"
        return "Please wait ..."

    def run_setup(self):
        if not Path(USB_SETUP_FILE).exists():
            logger.warning(f"File {USB_SETUP_FILE} not found, exiting ...")
            close_app()

        # Check if there's enough free space
        if not drive_has_enough_free_space(
            drive=MOUNT_POINT, space=get_tar_gz_extracted_size(USB_SETUP_FILE)
        ):
            self.state.update(
                {"run_state": RunStates.ERROR, "error": AppErrors.NOT_ENOUGH_SPACE}
            )
            return

        # Extract compressed file
        self.state.update({"run_state": RunStates.EXTRACTING_TAR})
        try:
            extract_file(file=USB_SETUP_FILE, destination=MOUNT_POINT)
        except Exception as e:
            logger.error(f"Error extracting {USB_SETUP_FILE} in {MOUNT_POINT}: {e}")
            self.state.update(
                {"run_state": RunStates.ERROR, "error": AppErrors.EXTRACTION}
            )
            return

        if os.environ.get("PT_USB_SETUP_SKIP_UPDATE", "0") == "0":
            version_before_update = get_package_version("pi-top-usb-setup")

            # Try to update packages
            self._update_packages()

            version_after_update = get_package_version("pi-top-usb-setup")

            # Restart service if it was updated
            if version_before_update != version_after_update:
                self._restart_service_and_skip_updates()

        if self.state.get("run_state") == RunStates.ERROR:
            return

        self.state.update({"run_state": RunStates.DONE})

    def _update_packages(self):
        if not Path(UPDATES_FOLDER).is_dir():
            logger.warning(f"Couldn't find {UPDATES_FOLDER}, skipping system update")
            return

        logger.info("Starting system update")
        for run_state, cmd in (
            (
                RunStates.UPDATING_SOURCES,
                f'sudo apt-get update -o Dir::Etc::sourcelist="{OFFLINE_APT_SOURCE}" -o Dir::Etc::sourceparts="-" -o APT::Get::List-Cleanup="0"',
            ),
            (
                RunStates.INSTALLING_UPDATES,
                f'sudo apt upgrade -y -o Dir::Etc::sourcelist="{OFFLINE_APT_SOURCE}" -o Dir::Etc::sourceparts="-" -o APT::Get::List-Cleanup="0"',
            ),
        ):
            try:
                logger.info(f"Updating packages: executing '{cmd}'")
                self.state.update({"run_state": run_state})
                output = run_command(cmd, timeout=60, check=False)
                logger.info(output)
            except Exception as e:
                logger.error(f"Update Error: {e}")
                self.state.update(
                    {"run_state": RunStates.ERROR, "error": AppErrors.UPDATE_ERROR}
                )
                return

        logger.info("Finished updating")

    def _current_progress(self):
        return self.state.get("run_state").value * 25

    def perform_action(self):
        run_state = self.state.get("run_state")
        if run_state in (RunStates.DONE, RunStates.ERROR):
            close_app()

    def _restart_service_and_skip_updates(self):
        logger.info("Package 'pi-top-usb-setup' was updated, restarting app...")

        # Write unit-file drop-in to skip dialog and updates
        content = """[Service]
Environment="PT_USB_SETUP_SKIP_UPDATE=1"
Environment="PT_USB_SETUP_SKIP_DIALOG=1"
"""
        folder = "/lib/systemd/system/pt-usb-setup.service.d"
        file = f"{folder}/10-skip-sections.conf"
        os.makedirs(folder, exist_ok=True)
        with open(file, "w") as f:
            f.write(content)

        # Reload systemd and restart service
        run_command("systemctl daemon-reload", timeout=10)
        run_command("systemctl restart pt-usb-setup", timeout=10)

    def render(self, image):
        offset = 5
        if self.state.get("run_state") not in (RunStates.DONE, RunStates.ERROR):
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
