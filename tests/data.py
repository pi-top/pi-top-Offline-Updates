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
    'nmcli connection add type wifi ifname wlan0 con-name "this-is-a-ssid" ssid "this-is-a-ssid" 802-11-wireless-security.key-mgmt OWE',
    'nmcli connection add type wifi ifname wlan0 con-name "this-is-a-ssid" ssid "this-is-a-ssid" 802-11-wireless.hidden yes 802-11-wireless-security.key-mgmt OWE',  # noqa: E501
    'nmcli connection add type wifi ifname wlan0 con-name "this-is-a-ssid" ssid "this-is-a-ssid" mode infra 802-11-wireless-security.key-mgmt wpa-psk 802-11-wireless-security.psk "this-is-a-password"',  # noqa: E501
    'nmcli connection add type wifi ifname wlan0 con-name "this-is-a-ssid" ssid "this-is-a-ssid" key-mgmt wpa-eap 802-1x.eap pwd 802-1x.identity this-is-a-username 802-1x.password "this-is-a-password"',  # noqa: E501
    'nmcli connection add type wifi ifname wlan0 con-name "this-is-a-ssid" ssid "this-is-a-ssid" 802-11-wireless-security.key-mgmt wpa-eap 802-1x.eap tls 802-1x.identity this-is-an-identity 802-1x.private-key /tmp/test.crt',  # noqa: E501
    'nmcli connection add type wifi ifname wlan0 con-name "this-is-a-ssid" ssid "this-is-a-ssid" 802-11-wireless-security.key-mgmt wpa-eap 802-1x.eap ttls 802-1x.anonymous-identity this-is-an-anonymous-identity 802-1x.identity this-is-a-username 802-1x.phase2-auth MSCHAPv2 802-1x.password "this-is-a-password"',  # noqa: E501
    'nmcli connection add type wifi ifname wlan0 con-name "this-is-a-ssid" ssid "this-is-a-ssid" 802-11-wireless-security.key-mgmt wpa-eap 802-1x.eap peap 802-1x.anonymous-identity this-is-an-anonymous-identity 802-1x.identity this-is-a-username 802-1x.phase2-auth MSCHAPv2 802-1x.password "this-is-a-password"',  # noqa: E501
]

wpasupplicant_resp = [
    """network {
        ssid="this-is-a-ssid"
        key_mgmt=OWE
}""",
    """network {
        ssid="this-is-a-ssid"
        scan_ssid=1
        key_mgmt=OWE
}""",
    """network {
        ssid="this-is-a-ssid"
        key-mgmt=WPA-PSK
        psk="this-is-a-password"
}""",
    """network {
        ssid="this-is-a-ssid"
        key_mgmt=WPA-EAP
        eap=PWD
        identity="this-is-a-username"
        password="this-is-a-password"
}""",
    """network {
        ssid="this-is-a-ssid"
        key_mgmt=WPA-EAP
        eap=TLS
        identity="this-is-an-identity"
        private_key="/tmp/test.crt"
}""",
    """network {
        ssid="this-is-a-ssid"
        key_mgmt=WPA-EAP
        eap=TTLS
        anonymous_identity="this-is-an-anonymous-identity"
        identity="this-is-a-username"
        phase2="auth=MSCHAPv2"
        password="this-is-a-password"
}""",
    """network {
        ssid="this-is-a-ssid"
        key_mgmt=WPA-EAP
        eap="PEAP"
        anonymous_identity="this-is-an-anonymous-identity"
        identity="this-is-a-username"
        phase2="MSCHAPv2"
        password="this-is-a-password"
}""",
]
