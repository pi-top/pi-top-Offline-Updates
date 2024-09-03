from sys import modules
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def patch_packages(mocker):
    modules_to_patch = [
        "pitop",
        "pitop.common.command_runner",
    ]
    for module in modules_to_patch:
        modules[module] = MagicMock()

    mocker.patch("pi_top_usb_setup.utils.run_command", return_value="")
