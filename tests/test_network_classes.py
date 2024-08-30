import pytest

network_data_array = [
    {
        "ssid": "this-is-a-ssid",
        "authentication": {
            "type": "OWE",
        },
    },
    {
        "ssid": "this-is-a-ssid",
        "hidden": True,
        "authentication": {
            "type": "OWE",
        },
    },
    {
        "ssid": "this-is-a-ssid",
        "authentication": {
            "type": "WPA_PERSONAL",
            "data": {
                "password": "this-is-a-password",
            },
        },
    },
    {
        "ssid": "this-is-a-ssid",
        "authentication": {
            "type": "WPA_ENTERPRISE",
            "data": {
                "authentication": "PWD",
                "username": "this-is-a-username",
                "password": "this-is-a-password",
            },
        },
    },
    {
        "ssid": "this-is-a-ssid",
        "authentication": {
            "type": "WPA_ENTERPRISE",
            "data": {
                "authentication": "TLS",
                "identity": "this-is-an-identity",
                "user_private_key": "this-is-a-user-private-key",
            },
        },
    },
    {
        "ssid": "this-is-a-ssid",
        "authentication": {
            "type": "WPA_ENTERPRISE",
            "data": {
                "authentication": "TTLS",
                "anonymous_identity": "this-is-an-anonymous-identity",
                "username": "this-is-a-username",
                "inner_authentication": "MSCHAPv2",
                "password": "this-is-a-password",
            },
        },
    },
    {
        "ssid": "this-is-a-ssid",
        "authentication": {
            "type": "WPA_ENTERPRISE",
            "data": {
                "authentication": "PEAP",
                "anonymous_identity": "this-is-an-anonymous-identity",
                "username": "this-is-a-username",
                "inner_authentication": "MSCHAPv2",
                "password": "this-is-a-password",
            },
        },
    },
]


nmcli_resp = [
    "nmcli connection add type wifi con-name this-is-a-ssid ssid this-is-a-ssid 802-11-wireless-security.key-mgmt OWE",
    "nmcli connection add type wifi con-name this-is-a-ssid ssid this-is-a-ssid 802-11-wireless.hidden yes 802-11-wireless-security.key-mgmt OWE",
    "nmcli connection add type wifi con-name this-is-a-ssid ssid this-is-a-ssid mode infa 802-11-wireless-security.key-mgmt wpa-psk 802-11-wireless-security.psk this-is-a-password",  # noqa: E501
    "nmcli connection add type wifi con-name this-is-a-ssid ssid this-is-a-ssid key-mgmt wpa-eap 802-1x.eap pwd 802-1x.identity this-is-a-username 802-1x.password this-is-a-password",  # noqa: E501
    "nmcli connection add type wifi con-name this-is-a-ssid ssid this-is-a-ssid 802-11-wireless-security.key-mgmt wpa-eap 802-1x.eap tls 802-1x.identity this-is-an-identity 802-1x.private-key /tmp/test.crt",  # noqa: E501
    "nmcli connection add type wifi con-name this-is-a-ssid ssid this-is-a-ssid 802-11-wireless-security.key-mgmt wpa-eap 802-1x.eap ttls 802-1x.anonymous-identity this-is-an-anonymous-identity 802-1x.identity this-is-a-username 802-1x.phase2-auth MSCHAPv2 802-1x.password this-is-a-password",  # noqa: E501
    "nmcli connection add type wifi con-name this-is-a-ssid ssid this-is-a-ssid 802-11-wireless-security.key-mgmt wpa-eap 802-1x.eap peap 802-1x.anonymous-identity this-is-an-anonymous-identity 802-1x.identity this-is-a-username 802-1x.phase2-auth MSCHAPv2 802-1x.password this-is-a-password",  # noqa: E501
]
wpasupplicant_resp = [
    """network {
        key_mgmt=OWE
}""",
    """network {
        key_mgmt=OWE
}""",
    """network {
        key-mgmt=WPA-PSK
        psk="this-is-a-password"
}""",
    """network {
        key_mgmt=WPA-EAP
        eap=PWD
        identity="this-is-a-username"
        password="this-is-a-password"
}""",
    """network {
        key_mgmt=WPA-EAP
        eap=TLS
        identity="this-is-an-identity"
        private_key="/tmp/test.crt"
}""",
    """network {
        key_mgmt=WPA-EAP
        eap=TTLS
        anonymous_identity="this-is-an-anonymous-identity"
        identity="this-is-a-username"
        phase2="auth=MSCHAPv2"
        password="this-is-a-password"
}""",
    """network {
        key_mgmt=WPA-EAP
        eap="PEAP"
        anonymous_identity="this-is-an-anonymous-identity"
        identity="this-is-a-username"
        phase2="MSCHAPv2"
        password="this-is-a-password"
}""",
]


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
