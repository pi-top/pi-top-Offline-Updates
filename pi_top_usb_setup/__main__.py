import logging
import os
from pathlib import Path
from signal import pause

import click
import click_logging

from .app import UsbSetupApp
from .common import COMPRESSED_SETUP_FILE

logger = logging.getLogger()
click_logging.basic_config(logger)


@click.command()
@click_logging.simple_verbosity_option(logger)
@click.version_option()
@click.option("--skip-dialog", is_flag=True)
@click.option("--skip-update", is_flag=True)
def main(skip_dialog, skip_update) -> None:
    if not Path(COMPRESSED_SETUP_FILE).exists():
        logger.warning(f"File {COMPRESSED_SETUP_FILE} not found, exiting ...")
        return

    if skip_dialog:
        os.environ["PT_USB_SETUP_SKIP_DIALOG"] = "1"
    if skip_update:
        os.environ["PT_USB_SETUP_SKIP_UPDATE"] = "1"

    app = UsbSetupApp()
    app.start()
    pause()


if __name__ == "__main__":
    main(prog_name="pt-usb-setup")  # pragma: no cover
