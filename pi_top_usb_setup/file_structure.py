import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from pitop.common.command_runner import run_command

from pi_top_usb_setup.utils import get_linux_distro

logger = logging.getLogger(__name__)


def get_default_certificate_paths() -> Dict[str, Dict[str, str]]:
    return {
        "ca-certificates": {
            "path": "/usr/local/share/ca-certificates",
            "command": "update-ca-certificates",
        }
    }


@dataclass
class MountPointStructure:
    """Represents a mount point where a USB drive was mounted, where the compressed setup file is expected to be found"""

    mount_point: str

    # Glob patterns
    USB_SETUP_FILENAME_GLOB: str = "pi-top-usb-setup*.tar.gz"

    def find_setup_files(self) -> List[Path]:
        # find all setup files in mount point that match the glob pattern, sorted by date
        return sorted(
            Path(self.mount_point).glob(self.USB_SETUP_FILENAME_GLOB),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

    def is_valid(self) -> bool:
        return len(self.find_setup_files()) > 0

    @classmethod
    def is_valid_mount_point(cls, mount_point: str) -> bool:
        return cls(mount_point).is_valid()

    def device(self) -> str:
        return run_command(
            f"findmnt -n -o SOURCE --target {self.mount_point}", timeout=5
        ).strip()

    def is_usb_drive(self) -> bool:
        device = self.device()
        return Path(device).exists() and device.startswith("/dev/sd")


@dataclass
class UsbSetupStructure:
    """Represents the file structure when the setup bundle is extracted into the system"""

    directory: str

    # Root folders
    SETUP_FOLDER: str = "pi-top-usb-setup"

    # Required files/folders
    CONFIG_FILE: str = "pi-top_config.json"
    FILES_FOLDER: str = "files"
    SCRIPTS_FOLDER: str = "scripts"
    UPDATES_FOLDER: str = "updates"
    UPDATES_BOOKWORM_FOLDER: str = "updates_bookworm"
    CERTIFICATES_FOLDER: str = "certificates"

    # Certificate structure
    CERTIFICATE_PATHS: Dict[str, Dict[str, str]] = field(
        default_factory=get_default_certificate_paths
    )

    def folder(self) -> Path:
        return Path(self.directory) / self.SETUP_FOLDER

    # All of the folders/files inside the setup folder
    def json_file(self) -> Path:
        return self.folder() / self.CONFIG_FILE

    def files_folder(self) -> Path:
        return self.folder() / self.FILES_FOLDER

    def scripts_folder(self) -> Path:
        return self.folder() / self.SCRIPTS_FOLDER

    def updates_folder(self) -> Path:
        is_bookworm = get_linux_distro() == "bookworm"
        return self.folder() / (
            self.UPDATES_BOOKWORM_FOLDER if is_bookworm else self.UPDATES_FOLDER
        )

    def certificates_folder(self) -> Path:
        return self.folder() / self.CERTIFICATES_FOLDER

    def is_valid(self) -> bool:
        # A valid config file is present; this can be
        # the case after the USB setup systemd service is restarted
        # after the package is updated by the app
        return self.json_file().exists()

    @classmethod
    def is_valid_directory(cls, directory: str) -> bool:
        return cls(directory).is_valid()
