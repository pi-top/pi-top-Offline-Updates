import pathlib
import shutil
import tempfile
from typing import Optional
from unittest.mock import MagicMock, Mock, call, patch

import pytest


@pytest.fixture
def mock_copy2():
    # mock pi_top_usb_setup.operations.copy2
    with patch("pi_top_usb_setup.operations.core.copy2") as copy_mock:
        yield copy_mock


@pytest.fixture
def mock_makedirs():
    with patch("pi_top_usb_setup.operations.core.makedirs") as makedirs_mock:
        yield makedirs_mock


@pytest.fixture
def mock_run_command(mock_pitop_imports):
    command_runner_mock = mock_pitop_imports["pitop.common.command_runner"]
    command_runner_mock.run_command = MagicMock()
    yield command_runner_mock.run_command


def create_structure(structure: dict, base_path: pathlib.Path):
    """
    Recursively create files and folders from a nested dictionary structure.

    Args:
        structure (dict): Dictionary representing folder/file structure.
        base_path (Path): Base directory to start creating the structure.
    """
    for name, content in structure.items():
        current_path = base_path / name
        if isinstance(content, dict):
            # It's a folder
            current_path.mkdir(parents=True, exist_ok=True)
            create_structure(content, current_path)
        else:
            # It's a file with optional content
            current_path.touch()
            if content:
                current_path.write_text(content)


@pytest.fixture
def create_mount_point():
    def _create_mount_point(files: dict):
        temp_dir = tempfile.mktemp()
        mount_point = pathlib.Path(temp_dir)
        mount_point.mkdir(exist_ok=True)

        create_structure(files, mount_point)
        return temp_dir

    yield _create_mount_point


@pytest.fixture
def operations(create_mount_point):
    created_dirs = []

    def _create_operations_obj(files: Optional[dict] = None):
        temp_dir = create_mount_point(files)
        created_dirs.append(temp_dir)

        from pi_top_usb_setup.file_structure import UsbSetupStructure
        from pi_top_usb_setup.operations import CoreOperations

        usb_setup_structure = UsbSetupStructure(temp_dir)
        return CoreOperations(usb_setup_structure)

    yield _create_operations_obj

    # Cleanup all created directories
    for temp_dir in created_dirs:
        shutil.rmtree(temp_dir)


def test_copy_files_creates_file_structure_in_target(
    mock_copy2, mock_makedirs, operations
):
    # Test basic copy
    structure = {
        "pi-top-usb-setup.tar.gz": "",
        "pi-top-usb-setup": {
            "files": {
                "tmp": {
                    "some_folder": {
                        "file.txt": "Hello, world!",
                    },
                    "file2.txt": "bla",
                },
            },
        },
    }
    app = operations(structure)
    app.copy_files()

    base_path = app.fs.files_folder()

    # Directories are created
    mock_makedirs.assert_has_calls(
        [
            call("/tmp", exist_ok=True),
            call("/tmp/some_folder", exist_ok=True),
        ]
    )

    # Copy operations occurred
    mock_copy2.assert_has_calls(
        [
            call(f"{base_path}/tmp/file2.txt", "/tmp/file2.txt"),
            call(f"{base_path}/tmp/some_folder/file.txt", "/tmp/some_folder/file.txt"),
        ]
    )


def test_copy_files_calls_progress_callback(mock_copy2, mock_makedirs, operations):
    # Test that progress callback is called
    structure = {
        "pi-top-usb-setup.tar.gz": "",
        "pi-top-usb-setup": {
            "files": {
                "tmp": {
                    "some_folder": {
                        "file.txt": "Hello, world!",
                        "other_folder": {
                            "file2.txt": "Hello, world!",
                        },
                    },
                    "file3.txt": "bla",
                    "file4.txt": "bla",
                },
            },
        },
    }
    progress_callback = Mock()
    app = operations(structure)
    app.copy_files(on_progress=progress_callback)
    progress_callback.assert_has_calls(
        [
            call(25.0),
            call(50.0),
            call(75.0),
            call(100.0),
        ]
    )


def test_copy_files_on_files_folder_without_files(mock_copy2, operations):
    # Test behavior when files folder is empty
    structure = {
        "pi-top-usb-setup.tar.gz": "",
        "pi-top-usb-setup": {
            "files": {},
        },
    }
    app = operations(structure)
    app.copy_files()
    mock_copy2.assert_not_called()


def test_copy_files_when_files_folder_does_not_exist(mock_copy2, operations):
    # Test behavior when files folder does not exist
    structure = {
        "pi-top-usb-setup.tar.gz": "",
        "pi-top-usb-setup": {},
    }
    app = operations(structure)
    app.copy_files()
    mock_copy2.assert_not_called()


def test_run_scripts_on_scripts_folder_without_files(mock_run_command, operations):
    # Test behavior when scripts folder is empty
    structure = {
        "pi-top-usb-setup.tar.gz": "",
        "pi-top-usb-setup": {
            "scripts": {},
        },
    }
    app = operations(structure)

    # reset mock_run_command - it's used in constructor
    mock_run_command.reset_mock()

    app.run_scripts()
    mock_run_command.assert_not_called()


def test_run_scripts_when_scripts_folder_does_not_exist(mock_run_command, operations):
    # Test behavior when scripts folder does not exist
    structure = {
        "pi-top-usb-setup.tar.gz": "",
        "pi-top-usb-setup": {},
    }
    app = operations(structure)

    # reset mock_run_command - it's used in constructor
    mock_run_command.reset_mock()

    app.run_scripts()
    mock_run_command.assert_not_called()


def test_run_scripts_in_order(mock_run_command, operations):
    # Scripts are run in order based on filename
    print(f"call: {call}")
    structure = {
        "pi-top-usb-setup.tar.gz": "",
        "pi-top-usb-setup": {
            "scripts": {
                "01-script.sh": "01",
                "02-script.sh": "02",
                "10-script.sh": "10",
                "99-script.sh": "99",
            },
        },
    }
    app = operations(structure)

    # reset mock_run_command - it's used in constructor
    mock_run_command.reset_mock()
    app.run_scripts()

    scripts_folder = app.fs.scripts_folder()
    mock_run_command.assert_has_calls(
        [
            call(f"chmod +x {scripts_folder}/01-script.sh", timeout=10),
            call(f"{scripts_folder}/01-script.sh", timeout=600),
            call(f"chmod +x {scripts_folder}/02-script.sh", timeout=10),
            call(f"{scripts_folder}/02-script.sh", timeout=600),
            call(f"chmod +x {scripts_folder}/10-script.sh", timeout=10),
            call(f"{scripts_folder}/10-script.sh", timeout=600),
            call(f"chmod +x {scripts_folder}/99-script.sh", timeout=10),
            call(f"{scripts_folder}/99-script.sh", timeout=600),
        ]
    )


def test_run_scripts_executes_callback_on_progress(operations):
    # on_progress callback is called with correct progress
    structure = {
        "pi-top-usb-setup.tar.gz": "",
        "pi-top-usb-setup": {
            "scripts": {
                "01-script.sh": "01",
                "02-script.sh": "02",
                "10-script.sh": "10",
                "99-script.sh": "99",
            },
        },
    }
    app = operations(structure)

    on_progress_callback = Mock()
    app.run_scripts(on_progress=on_progress_callback)

    on_progress_callback.assert_has_calls(
        [
            call(25.0),
            call(50.0),
            call(75.0),
            call(100.0),
        ]
    )


def test_run_scripts_on_error_raises_exception(mock_run_command, operations):
    # on error, the script is skipped and the next script is executed
    structure = {
        "pi-top-usb-setup.tar.gz": "",
        "pi-top-usb-setup": {
            "scripts": {
                "01-script.sh": "01",
                "02-script.sh": "02",
            },
        },
    }
    app = operations(structure)

    # reset mock_run_command - it's used in constructor
    mock_run_command.reset_mock()

    def raise_on_third_call(*args, **kwargs):
        if mock_run_command.call_count == 3:
            raise Exception("Error")

    mock_run_command.side_effect = raise_on_third_call
    with pytest.raises(Exception):
        app.run_scripts()

    scripts_folder = app.fs.scripts_folder()
    mock_run_command.assert_has_calls(
        [
            call(f"chmod +x {scripts_folder}/01-script.sh", timeout=10),
            call(f"{scripts_folder}/01-script.sh", timeout=600),
            call(f"chmod +x {scripts_folder}/02-script.sh", timeout=10),
        ]
    )


def test_install_certificates_when_no_certificates_folder_exists(
    mock_copy2, mock_run_command, operations
):
    # Test behavior when certificates folder does not exist
    structure = {
        "pi-top-usb-setup.tar.gz": "",
        "pi-top-usb-setup": {},
    }
    app = operations(structure)
    app.install_certificates()
    mock_copy2.assert_not_called()
    mock_run_command.assert_not_called()


def test_install_certificates_when_folder_is_empty(
    mock_run_command, mock_copy2, operations
):
    # Test behavior when certificates folder is empty
    structure = {
        "pi-top-usb-setup.tar.gz": "",
        "pi-top-usb-setup": {
            "certificates": {},
        },
    }
    app = operations(structure)
    # reset mock_run_command - it's used in constructor
    mock_run_command.reset_mock()

    app.install_certificates()
    mock_copy2.assert_not_called()
    mock_run_command.assert_not_called()


def test_install_certificates_when_ca_certificates_folder_is_empty(
    mock_run_command, mock_copy2, operations
):
    # Test behavior when the ca-certificates folder inside the certificates folder is empty
    structure = {
        "pi-top-usb-setup.tar.gz": "",
        "pi-top-usb-setup": {
            "certificates": {
                "ca-certificates": {},
            },
        },
    }
    app = operations(structure)
    # reset mock_run_command - it's used in constructor
    mock_run_command.reset_mock()

    app.install_certificates()
    mock_copy2.assert_not_called()
    mock_run_command.assert_not_called()


def test_install_certificates_when_invalid_folder_is_found(
    mock_run_command, mock_copy2, operations
):
    # Test behavior when an invalid folder is found inside the certificates folder
    structure = {
        "pi-top-usb-setup.tar.gz": "",
        "pi-top-usb-setup": {
            "certificates": {
                "invalid-folder": {
                    "client.pem": "",
                },
            },
        },
    }
    app = operations(structure)

    # reset mock_run_command - it's used in constructor
    mock_run_command.reset_mock()

    app.install_certificates()
    mock_copy2.assert_not_called()
    mock_run_command.assert_not_called()


def test_install_certificates_when_valid_folder_is_found(
    mock_run_command, mock_copy2, mock_makedirs, operations
):
    # Test behavior when a valid folder is found inside the certificates folder
    structure = {
        "pi-top-usb-setup.tar.gz": "",
        "pi-top-usb-setup": {
            "certificates": {
                "ca-certificates": {
                    "client.pem": "",
                    "server.pem": "",
                },
            },
        },
    }
    app = operations(structure)

    # reset mock_run_command - it's used in constructor
    mock_run_command.reset_mock()

    app.install_certificates()

    # The folder is created
    mock_makedirs.assert_has_calls(
        [
            call("/usr/local/share/ca-certificates", exist_ok=True),
        ]
    )
    # Files are copied to the correct folder
    mock_copy2.assert_has_calls(
        [
            call(
                f"{app.fs.certificates_folder()}/ca-certificates/server.pem",
                "/usr/local/share/ca-certificates",
            ),
            call(
                f"{app.fs.certificates_folder()}/ca-certificates/client.pem",
                "/usr/local/share/ca-certificates",
            ),
        ]
    )
    # The associated command is run
    mock_run_command.assert_called_once_with("update-ca-certificates", timeout=60)
