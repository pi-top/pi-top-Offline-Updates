import os
import stat
import time
from unittest.mock import Mock, call, patch

import pytest


@pytest.fixture
def print_folder_recursively():
    from pi_top_usb_setup.utils import (
        print_folder_recursively as print_folder_recursively_func,
    )

    yield print_folder_recursively_func


@patch("pi_top_usb_setup.utils.logging")
@patch("pi_top_usb_setup.utils.os")
@patch("pi_top_usb_setup.utils.pwd")
@patch("pi_top_usb_setup.utils.grp")
@patch("pi_top_usb_setup.utils.time")
def test_print_folder_recursively_success(
    mock_time, mock_grp, mock_pwd, mock_os, mock_logging, print_folder_recursively
):
    # Setup mock returns
    mock_os.walk.return_value = [
        ("/some_folder", ["dir1"], ["file1.txt"]),
        ("/some_folder/dir1", [], ["file2.txt"]),
    ]

    mock_stat = Mock()
    mock_stat.st_mode = stat.S_IFREG | 0o644
    mock_stat.st_nlink = 1
    mock_stat.st_uid = 1000
    mock_stat.st_gid = 1000
    mock_stat.st_size = 1234
    mock_stat.st_mtime = 1625097600

    mock_os.lstat.return_value = mock_stat
    mock_os.path.join = os.path.join  # 'unmock' join function

    mock_pwd.getpwuid.return_value.pw_name = "testuser"
    mock_grp.getgrgid.return_value.gr_name = "testgroup"
    mock_time.localtime.return_value = time.struct_time(
        (2021, 7, 1, 12, 0, 0, 3, 182, 0)
    )
    mock_time.strftime.return_value = "Jul 01 12:00"

    # Call function
    print_folder_recursively("/some_folder")

    # Verify logging calls
    mock_logging.info.assert_has_calls(
        [
            call("\n/some_folder:"),
            call("-rw-r--r-- 1 testuser testgroup     1234 Jul 01 12:00 dir1"),
            call("-rw-r--r-- 1 testuser testgroup     1234 Jul 01 12:00 file1.txt"),
            call("\n/some_folder/dir1:"),
            call("-rw-r--r-- 1 testuser testgroup     1234 Jul 01 12:00 file2.txt"),
        ]
    )


@patch("pi_top_usb_setup.utils.logging")
@patch("pi_top_usb_setup.utils.os")
def test_print_folder_recursively_error(
    mock_os, mock_logging, print_folder_recursively
):
    # Setup mock to raise an exception
    mock_os.walk.return_value = [("/sample_folder", [], ["file1.txt"])]
    mock_os.path.join = os.path.join
    mock_os.lstat.side_effect = PermissionError("Permission denied")

    # Call function
    print_folder_recursively("/sample_folder")

    # Verify error was logged
    mock_logging.error.assert_called_once_with(
        "Error reading /sample_folder/file1.txt: Permission denied"
    )
