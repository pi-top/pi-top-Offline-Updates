import logging
import os
from pathlib import Path
from typing import Callable, Optional

from .utils import Process

logger = logging.getLogger(__name__)


class CustomAptSource:
    def __init__(self, path_to_repo: Optional[str]) -> None:
        self.path = path_to_repo
        self.source = "/tmp/offline-apt-source.list"
        self.source_path = Path(self.source)
        self.source_path.unlink(missing_ok=True)

    def __enter__(self):
        if not self.path:
            return None

        logger.info(f"Creating offline apt source in {self.source}")
        with open(self.source, "w") as file:
            file.write(f"deb [trusted=yes] file:{self.path} ./")
        return self.source

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.source_path.unlink(missing_ok=True)


class SystemUpdater:
    def __init__(
        self,
        apt_repository: Optional[str] = None,
        on_progress: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ) -> None:
        self.apt_repository = apt_repository
        self.on_progress = on_progress
        self.on_error = on_error

    def _message_handler(self, message):
        # Handle APT messages to provide relevant information to user
        # https://github.com/Debian/apt/blob/main/doc/progress-reporting.md#pmstatus

        logger.info(f"{message}")

        type, *other = message.split(":")
        if type == "pmstatus" or type == "error":
            pkg_name, total_percentage, description = other
            if callable(self.on_progress):
                self.on_progress(float(total_percentage))
            if callable(self.on_error) and type == "error":
                self.on_error(description)
        else:
            logger.debug(f"Unsupported APT message type: {type}")

    def _run_cmd(self, cmd: str) -> None:
        def updates_env():
            env = os.environ.copy()
            env["DEBIAN_FRONTEND"] = "noninteractive"
            return env

        with CustomAptSource(self.apt_repository) as apt_source:
            if apt_source:
                cmd += f' -o Dir::Etc::sourcelist="{apt_source}" -o Dir::Etc::sourceparts="-" -o APT::Get::List-Cleanup="0"'

            # Send status reports to stdout
            cmd += " -o APT::Status-Fd=1"

            exit_code = Process(
                cmd,
                timeout=3600,
                stderr_callback=self.on_error,
                stdout_callback=self._message_handler,
            ).run(environment=updates_env())
            if exit_code != 0:
                raise Exception(f"Command '{cmd}' exited with code '{exit_code}'")

    def update(self) -> None:
        self._run_cmd("sudo apt-get update")

    def upgrade(self) -> None:
        self._run_cmd("sudo apt-get dist-upgrade -y")
