import pytest

from tests.data import network_data_array, nmcli_resp, wpasupplicant_resp


def test_success(mocker):
    mocker.patch(
        "pi_top_usb_setup.network.generate_filename", return_value="/tmp/test.crt"
    )
    from pi_top_usb_setup.network import Network

    for input, nmcli_r, wpasupplicant_r in zip(
        network_data_array, nmcli_resp, wpasupplicant_resp
    ):
        n = Network.from_dict(input)
        assert n.to_nmcli() == nmcli_r
        assert n.to_wpasupplicant_conf() == wpasupplicant_r


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
