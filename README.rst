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

Each step of the setup process is optional and can be disabled by setting the corresponding
key to `false` in the file located in `/var/lib/pi-top-usb-setup/state.cfg`.

-------------------------------------------
File structure for pi-top-usb-setup.tar.gz
-------------------------------------------

.. code-block::

    pi-top-usb-setup/
        pi-top_config.json
        certificates/
            # certificates to install
            ca-certificates/
                cert1.crt
                cert2.crt
                ...
        files/
            # files to copy to root of pi-top
            # e.g. to copy certificates create this nested folder structure
            usr/
                local/
                    share/
                        ca-certificates/
                            cert1.crt
                            cert2.crt
                            ...
        scripts/
            # shell scripts to run
            01-update-certs.sh
            ...
        updates/
        updates_bookworm/


--------
JSON
--------

Sample JSON file to configure the device:

.. code-block:: json

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


--------------------------------
State configuration file
--------------------------------

The application configuration file is located in `/var/lib/pi-top-usb-setup/state.cfg` and
contains the state of the setup process.

A sample of the file with the default values is the following:

.. code-block:: text

    [app]
    install_update = true
    install_certificates = true
    copy_files = true
    run_scripts = true
    install_network = true
    complete_onboarding = true
    configure_device = true
