from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_pitop_imports():
    """Mock all pi-top related imports"""
    # Create mock for backend module
    mock_backend = MagicMock()
    mock_helpers = MagicMock()

    # Create mock for finalise module
    mock_finalise = MagicMock()
    mock_finalise.deprioritise_openbox_session = MagicMock()
    mock_finalise.disable_ap_mode = MagicMock()
    mock_finalise.enable_firmware_updater_service = MagicMock()
    mock_finalise.enable_further_link_service = MagicMock()
    mock_finalise.enable_pt_miniscreen = MagicMock()
    mock_finalise.onboarding_completed = MagicMock()
    mock_finalise.restore_files = MagicMock()
    mock_finalise.stop_first_boot_app_autostart = MagicMock()
    mock_finalise.update_eeprom = MagicMock()

    # Create mock for keyboard module
    mock_keyboard = MagicMock()
    mock_keyboard.set_keyboard_layout = MagicMock()

    # Create mock for language module
    mock_language = MagicMock()
    mock_language.set_locale = MagicMock()

    # Create mock for registration module
    mock_registration = MagicMock()
    mock_registration.set_registration_email = MagicMock()

    # Create mock for timezone module
    mock_timezone = MagicMock()
    mock_timezone.set_timezone = MagicMock()

    # Create mock for wifi country module
    mock_wifi_country = MagicMock()
    mock_wifi_country.set_wifi_country = MagicMock()

    # Add mocks to helpers
    mock_helpers.finalise = mock_finalise
    mock_helpers.keyboard = mock_keyboard
    mock_helpers.language = mock_language
    mock_helpers.registration = mock_registration
    mock_helpers.timezone = mock_timezone
    mock_helpers.wifi_country = mock_wifi_country

    # Add helpers to backend
    mock_backend.helpers = mock_helpers

    # Create mock for main package
    mock_pt_os_web_portal = MagicMock()
    mock_pt_os_web_portal.backend = mock_backend

    mocks = {
        "pitop": MagicMock(),
        "pitop.common.command_runner": MagicMock(),
        "pt_os_web_portal": mock_pt_os_web_portal,
        "pt_os_web_portal.backend": mock_backend,
        "pt_os_web_portal.backend.helpers.finalise": mock_finalise,
        "pt_os_web_portal.backend.helpers.keyboard": mock_keyboard,
        "pt_os_web_portal.backend.helpers.language": mock_language,
        "pt_os_web_portal.backend.helpers.registration": mock_registration,
        "pt_os_web_portal.backend.helpers.timezone": mock_timezone,
        "pt_os_web_portal.backend.helpers.wifi_country": mock_wifi_country,
    }

    with patch.dict("sys.modules", mocks):
        yield mocks


@pytest.fixture(autouse=True)
def patch_network_internals(mocker):
    mocker.patch("pi_top_usb_setup.network.CERT_FOLDER", "/tmp")
    mocker.patch("pi_top_usb_setup.network.get_linux_distro", return_value="bookworm")
