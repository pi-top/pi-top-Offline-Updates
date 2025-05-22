connection_dict_arr = [
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
                "user_private_key": {
                    "filename": "user.key",
                    "content": "this-is-the-content",
                },
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

nmcli_str_arr = [
    "nmcli connection add type wifi ifname wlan0 con-name 'PT-USB-SETUP-this-is-a-ssid' ssid 'this-is-a-ssid' 802-11-wireless-security.key-mgmt OWE",
    "nmcli connection add type wifi ifname wlan0 con-name 'PT-USB-SETUP-this-is-a-ssid' ssid 'this-is-a-ssid' 802-11-wireless.hidden yes 802-11-wireless-security.key-mgmt OWE",  # noqa: E501
    "nmcli connection add type wifi ifname wlan0 con-name 'PT-USB-SETUP-this-is-a-ssid' ssid 'this-is-a-ssid' mode infra 802-11-wireless-security.key-mgmt wpa-psk 802-11-wireless-security.psk 'this-is-a-password'",  # noqa: E501
    "nmcli connection add type wifi ifname wlan0 con-name 'PT-USB-SETUP-this-is-a-ssid' ssid 'this-is-a-ssid' key-mgmt wpa-eap 802-1x.eap pwd 802-1x.identity 'this-is-a-username' 802-1x.password 'this-is-a-password'",  # noqa: E501
    "nmcli connection add type wifi ifname wlan0 con-name 'PT-USB-SETUP-this-is-a-ssid' ssid 'this-is-a-ssid' 802-11-wireless-security.key-mgmt wpa-eap 802-1x.eap tls 802-1x.identity 'this-is-an-identity' 802-1x.private-key '/tmp/user.key'",  # noqa: E501
    "nmcli connection add type wifi ifname wlan0 con-name 'PT-USB-SETUP-this-is-a-ssid' ssid 'this-is-a-ssid' 802-11-wireless-security.key-mgmt wpa-eap 802-1x.eap ttls 802-1x.anonymous-identity 'this-is-an-anonymous-identity' 802-1x.identity 'this-is-a-username' 802-1x.phase2-auth MSCHAPv2 802-1x.password 'this-is-a-password'",  # noqa: E501
    "nmcli connection add type wifi ifname wlan0 con-name 'PT-USB-SETUP-this-is-a-ssid' ssid 'this-is-a-ssid' 802-11-wireless-security.key-mgmt wpa-eap 802-1x.eap peap 802-1x.identity 'this-is-a-username' 802-1x.phase2-auth MSCHAPv2 802-1x.anonymous-identity 'this-is-an-anonymous-identity' 802-1x.password 'this-is-a-password'",  # noqa: E501
]

wpasupplicant_str_arr = [
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
        private_key="/tmp/user.key"
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

connect_cmds_arr = [
    ['raspi-config nonint do_wifi_ssid_passphrase "this-is-a-ssid"  0 0'],
    ['raspi-config nonint do_wifi_ssid_passphrase "this-is-a-ssid"  1 0'],
    [
        'raspi-config nonint do_wifi_ssid_passphrase "this-is-a-ssid" "this-is-a-password" 0 0'
    ],
    [
        "nmcli connection add type wifi ifname wlan0 con-name 'PT-USB-SETUP-this-is-a-ssid' ssid 'this-is-a-ssid' key-mgmt wpa-eap 802-1x.eap pwd 802-1x.identity 'this-is-a-username' 802-1x.password 'this-is-a-password'",  # noqa: E501
        "nmcli connection up 'PT-USB-SETUP-this-is-a-ssid'",
    ],
    [
        "nmcli connection add type wifi ifname wlan0 con-name 'PT-USB-SETUP-this-is-a-ssid' ssid 'this-is-a-ssid' 802-11-wireless-security.key-mgmt wpa-eap 802-1x.eap tls 802-1x.identity 'this-is-an-identity' 802-1x.private-key '/tmp/user.key'",  # noqa: E501
        "nmcli connection up 'PT-USB-SETUP-this-is-a-ssid'",
    ],
    [
        "nmcli connection add type wifi ifname wlan0 con-name 'PT-USB-SETUP-this-is-a-ssid' ssid 'this-is-a-ssid' 802-11-wireless-security.key-mgmt wpa-eap 802-1x.eap ttls 802-1x.anonymous-identity 'this-is-an-anonymous-identity' 802-1x.identity 'this-is-a-username' 802-1x.phase2-auth MSCHAPv2 802-1x.password 'this-is-a-password'",  # noqa: E501
        "nmcli connection up 'PT-USB-SETUP-this-is-a-ssid'",
    ],
    [
        "nmcli connection add type wifi ifname wlan0 con-name 'PT-USB-SETUP-this-is-a-ssid' ssid 'this-is-a-ssid' 802-11-wireless-security.key-mgmt wpa-eap 802-1x.eap peap 802-1x.identity 'this-is-a-username' 802-1x.phase2-auth MSCHAPv2 802-1x.anonymous-identity 'this-is-an-anonymous-identity' 802-1x.password 'this-is-a-password'",  # noqa: E501
        "nmcli connection up 'PT-USB-SETUP-this-is-a-ssid'",
    ],
]

valid_data_arr = []
for i, con in enumerate(connection_dict_arr):
    valid_data_arr.append(
        {
            "network_data": con,
            "nmcli_str": nmcli_str_arr[i],
            "wpasupplicant_str": wpasupplicant_str_arr[i],
            "connect_str_arr": connect_cmds_arr[i],
        }
    )
