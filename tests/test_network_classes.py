import pytest

from tests.data import valid_data_arr


def file_content(file: str) -> str:
    with open(file) as f:
        return f.read()


def compare_files(file1: str, file2: str) -> bool:
    return file_content(file1) == file_content(file2)


def test_success(mocker):
    from pi_top_usb_setup.network import Network

    for test_dict in valid_data_arr:
        n = Network.from_dict(test_dict["network_data"])
        assert n.to_nmcli() == test_dict["nmcli_str"]
        assert n.to_wpasupplicant_conf() == test_dict["wpasupplicant_str"]


def test_wrong_arguments():
    # doesn't crash if provided with wrong arguments; only takes what's needed from data
    from pi_top_usb_setup.network import Network, PWDAuthentication, WpaEnterprise

    data = {
        "ssid": "this-is-a-ssid",
        "authentication": {
            "type": "WPA_ENTERPRISE",
            "identity": "this-is-an-identity",
            "data": {
                "authentication": "PWD",
                "username": "this-is-a-username",
                "password": "this-is-a-password",
                "ca_cert": "this-is-not-needed",
                "inner_authentication": "this-is-not-needed",
            },
        },
    }
    n = Network.from_dict(data)
    assert n.ssid == "this-is-a-ssid"
    assert isinstance(n.authentication, WpaEnterprise)
    assert isinstance(n.authentication.authentication, PWDAuthentication)
    assert hasattr(n, "identity") is False
    assert hasattr(n.authentication.authentication, "inner_authentication") is False


def test_fails_on_missing_arguments():
    # throws an error if required arguments are missing
    from pi_top_usb_setup.network import Network

    data = {
        "ssid": "this-is-a-ssid",
        "authentication": {
            "type": "WPA_ENTERPRISE",
            "identity": "this-is-an-identity",
            "data": {
                "authentication": "PWD",
                "password": "im-missing-username",
            },
        },
    }
    with pytest.raises(TypeError):
        Network.from_dict(data)


def test_connect_commands(mocker):
    # check commands run when connecting to network
    run_command_mock = mocker.patch("pi_top_usb_setup.network.run_command")
    from pi_top_usb_setup.network import Network

    for test_data in valid_data_arr:
        n = Network.from_dict(test_data["network_data"])
        n.connect()
        for cmd in test_data["connect_str_arr"]:
            run_command_mock.assert_any_call(cmd, timeout=30, check=True)
        run_command_mock.reset_mock()


def test_keys_and_certs_are_written_to_disk(mocker):
    from pi_top_usb_setup.network import Network

    run_command_mock = mocker.patch("pi_top_usb_setup.network.run_command")

    data = {
        "ssid": "an-enterprise-ssid",
        "authentication": {
            "type": "WPA_ENTERPRISE",
            "data": {
                "authentication": "TLS",
                "identity": "sampleUser",
                "user_private_key_password": "whatever",
                "user_private_key": {
                    "filename": "user.key",
                    "content": file_content("tests/certs/user.key"),
                },
                "user_cert": {
                    "filename": "client.pem",
                    "content": file_content("tests/certs/client.pem"),
                },
            },
        },
    }
    n = Network.from_dict(data)
    # Destination folder is created
    run_command_mock.assert_any_call("mkdir -p /tmp", timeout=10, check=True)
    # Files written to disk match the content
    assert compare_files(
        n.authentication.authentication.user_private_key.path,
        f"tests/certs/{data['authentication']['data']['user_private_key']['filename']}",
    )
    assert compare_files(
        n.authentication.authentication.user_cert.path,
        f"tests/certs/{data['authentication']['data']['user_cert']['filename']}",
    )


def test_deletes_connection_if_exists(mocker):
    # connection is removed if it already exists
    from pi_top_usb_setup.network import Network

    Network.exists = lambda _: True
    run_command_mock = mocker.patch("pi_top_usb_setup.network.run_command")

    data = {
        "ssid": "this-is-a-ssid",
        "authentication": {
            "type": "WPA_ENTERPRISE",
            "identity": "this-is-an-identity",
            "data": {
                "authentication": "PWD",
                "username": "this-is-a-username",
                "password": "this-is-a-password",
            },
        },
    }
    n = Network.from_dict(data)
    n.connect()

    run_command_mock.assert_any_call(
        f"nmcli connection down 'PT-USB-SETUP-{data['ssid']}'", timeout=30, check=True
    )
    run_command_mock.assert_any_call(
        f"nmcli connection delete 'PT-USB-SETUP-{data['ssid']}'", timeout=30, check=True
    )
