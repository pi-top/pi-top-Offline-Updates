#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os import environ

import setuptools

if __name__ == "__main__":
    setuptools.setup(
        scripts=["extra/handle-usb-drive-for-pi-top-setup"],
        version=environ.get("PYTHON_PACKAGE_VERSION", "0.0.1").replace('"', ""),
    )
