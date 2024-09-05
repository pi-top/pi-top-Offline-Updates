================
pi-top USB Setup
================

-----
About
-----


Application that configures a pi-top using an USB drive, installing offline updates
and setting up locales, language and wi-fi networks.

When a USB drive is plugged to the system with a file called `pi-top-usb-setup.tar.gz`,
a udev rule starts a systemd service that extracts the tarball and runs the setup script.

The setup script updates the system using a local apt repository with the files in the USB drive,
and the uses a JSON file to set the locales, language, keyboard layout and wi-fi network.

--------
JSON
--------

Format of the JSON file:

```json
{
    "language": "en_GB",
    "country": "GB",
    "time_zone": "Europe/London",
    "keyboard_layout": ["gb", null],
    "email": "my@email.com",
    "network": {
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
}
