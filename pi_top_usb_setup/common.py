from pathlib import Path

HERE = Path(__file__).parent.resolve()
OFFLINE_APT_SOURCE = f"{HERE}/extra/pi-top-offline.list"

MOUNT_POINT = "/tmp/pitop-usb-setup"
COMPRESSED_SETUP_FILE = f"{MOUNT_POINT}/pi-top-usb-setup.tar.gz"
USB_SETUP_FILE = f"{MOUNT_POINT}/pi-top-usb-setup.tar.gz"
UPDATES_FOLDER = f"{MOUNT_POINT}/pi-top-usb-setup/updates"
