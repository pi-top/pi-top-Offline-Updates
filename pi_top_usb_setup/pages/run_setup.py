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

from pi_top_usb_setup.utils import (
    AppPaths,
    OfflineAptSource,
    ProcessLogger,
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

        try:
            mount_point = os.environ["PT_USB_SETUP_MOUNT_POINT"]
            self.paths = AppPaths(mount_point)
        except Exception as e:
            logger.error(f"{e}")
            raise e

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

    def run_setup(self):
        try:
            # Extract compressed files
            self._extract_file(
                file=self.paths.USB_SETUP_FILE, destination=self.paths.MOUNT_POINT
            )
            self._extract_file(
                file=self.paths.UPDATES_TAR_FILE, destination=self.paths.SETUP_FOLDER
            )

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
            drive=self.paths.MOUNT_POINT, space=get_tar_gz_extracted_size(file)
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

        with OfflineAptSource(self.paths.UPDATES_FOLDER) as apt_source:
            for run_state, cmd in (
                (
                    RunStates.UPDATING_SOURCES,
                    f'sudo apt-get update -o Dir::Etc::sourcelist="{apt_source}" -o Dir::Etc::sourceparts="-" -o APT::Get::List-Cleanup="0"',
                ),
                (
                    RunStates.INSTALLING_UPDATES,
                    f'sudo apt list --upgradable -o Dir::Etc::sourcelist="{apt_source}" -o Dir::Etc::sourceparts="-" -o APT::Get::List-Cleanup="0"',
                ),
                (
                    RunStates.INSTALLING_UPDATES,
                    f'sudo apt-get dist-upgrade -y -o Dir::Etc::sourcelist="{apt_source}" -o Dir::Etc::sourceparts="-" -o APT::Get::List-Cleanup="0"',
                ),
            ):
                try:
                    self.state.update({"run_state": run_state})
                    process = ProcessLogger(cmd, timeout=3600)

                    def updates_env():
                        env = os.environ.copy()
                        env["DEBIAN_FRONTEND"] = "noninteractive"
                        return env

                    exit_code = process.run(environment=updates_env())
                    if exit_code != 0:
                        raise Exception(
                            f"Command '{cmd}' exited with code '{exit_code}'"
                        )
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
        return self.state.get("run_state").value * 25

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

    def perform_action(self):
        run_state = self.state.get("run_state")
        if run_state in (RunStates.DONE, RunStates.ERROR):
            umount_usb_drive(self.paths.MOUNT_POINT)
            close_app()

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
