import logging
import os
from signal import pause

import click
import click_logging
from pitop.common.command_runner import run_command

from pi_top_usb_setup.app import UsbSetupApp
from pi_top_usb_setup.usb_file_structure import UsbSetupStructure

logger = logging.getLogger()
click_logging.basic_config(logger)


def is_device(path: str) -> bool:
    return path.startswith("/dev/")


def find_mount_point(device: str) -> str:
    try:
        return run_command(f"findmnt -n -o TARGET {device}", timeout=5).strip()
    except Exception as e:
        raise Exception(f"Error finding mount point for {device}: {e}") from e


@click.command()
@click_logging.simple_verbosity_option(logger)
@click.version_option()
@click.argument("mount_point_or_device", type=click.Path(exists=True))
@click.option("--skip-dialog", is_flag=True)
def main(
    mount_point_or_device,
    skip_dialog,
) -> None:
    mount_point = mount_point_or_device
    if is_device(mount_point_or_device):
        mount_point = find_mount_point(mount_point_or_device)
        logger.info(f"Mount point for {mount_point_or_device} is {mount_point}")

    try:
        UsbSetupStructure(mount_point)
    except Exception as e:
        logger.error(f"{e}")
        return

    if skip_dialog:
        os.environ["PT_USB_SETUP_SKIP_DIALOG"] = "1"
    if mount_point:
        os.environ["PT_USB_SETUP_MOUNT_POINT"] = mount_point

    app = UsbSetupApp()
    app.start()
    pause()


if __name__ == "__main__":
    main(prog_name="pt-usb-setup")  # pragma: no cover
