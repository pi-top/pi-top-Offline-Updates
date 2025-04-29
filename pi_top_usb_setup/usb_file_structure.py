import logging
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import mkdtemp
from typing import Dict, List

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
class UsbSetupStructure:
    mount_point: str
    temp_folder_path: Path = field(init=False)

    def __post_init__(self):
        self.temp_folder_path = None

        if len(self.find_setup_files()) == 0:
            # Couldn't find a USB setup file in the mount_point which might be the case when
            # the app is restarted after the package is updated by the app.
            # If that's the case, this is already a temporary folder, so try to use it...
            self.temp_folder_path = Path(self.mount_point).parent
        else:
            self.temp_folder_path = Path(mkdtemp())
        assert (
            self.is_valid()
        ), f"Couldn't find find a valid USB setup file in {self.mount_point}"

    # Glob patterns
    USB_SETUP_FILENAME_GLOB: str = "pi-top-usb-setup*.tar.gz"

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

    # Folder that will be used to extract the setup file into
    def temp_folder(self) -> Path:
        return self.temp_folder_path

    def folder(self) -> Path:
        return self.temp_folder() / self.SETUP_FOLDER

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

    def find_setup_files(self) -> List[Path]:
        # find all setup files in mount point that match the glob pattern, sorted by date
        return sorted(
            Path(self.mount_point).glob(self.USB_SETUP_FILENAME_GLOB),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

    def is_valid(self) -> bool:
        return any(
            [
                # A compressed setup file should be present in the mount point
                len(self.find_setup_files()) > 0,
                # OR a config file is present in the mount point; this can be
                # the case after the USB setup systemd service is restarted
                # after the package is updated by the app
                self.json_file().exists(),
            ]
        )

    @classmethod
    def is_valid_mount_point(cls, mount_point: str) -> bool:
        return cls(mount_point).is_valid()
