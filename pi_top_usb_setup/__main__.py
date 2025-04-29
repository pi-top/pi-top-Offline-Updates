import logging
import os
from signal import pause

import click
import click_logging

from pi_top_usb_setup.app import UsbSetupApp
from pi_top_usb_setup.usb_file_structure import UsbSetupStructure

logger = logging.getLogger()
click_logging.basic_config(logger)


@click.command()
@click_logging.simple_verbosity_option(logger)
@click.version_option()
@click.argument("mount_point", type=click.Path(exists=True))
@click.option("--skip-dialog", is_flag=True)
def main(
    mount_point,
    skip_dialog,
) -> None:

    if not UsbSetupStructure.is_valid_mount_point(mount_point):
        raise Exception(f"Couldn't find a valid USB update bundle in {mount_point}")

    if skip_dialog:
        os.environ["PT_USB_SETUP_SKIP_DIALOG"] = "1"
    if mount_point:
        os.environ["PT_USB_SETUP_MOUNT_POINT"] = mount_point

    app = UsbSetupApp()
    app.start()
    pause()


if __name__ == "__main__":
    main(prog_name="pt-usb-setup")  # pragma: no cover
