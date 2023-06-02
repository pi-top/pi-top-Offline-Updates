#!/bin/bash

PACKAGES_FOLDER="packages"
PACKAGES_FILE="packages.list"
COMPRESSED_FILE="packages.tar.gz"

install_dependencies() {
    apt update
    apt install -y \
        dpkg-dev \
        mawk \
        gzip \
        tar
}

generate_packages_list() {
    # List all installed packages
    dpkg-query -W -f='${Status} ${package}=${version}\n' | grep "^install ok installed" | awk '{print $4}' >"${PACKAGES_FILE}"
}

download_packages() {
    cd "${PACKAGES_FOLDER}"
    while IFS= read -r package; do
        DOWNLOAD_CMD="apt download ${package}"
        eval "${DOWNLOAD_CMD}"

        # Retry on failure
        while [ $? -ne 0 ]; do
            echo "Failed to download packlage ${package}. Retrying..."
            sleep 1
            eval "${DOWNLOAD_CMD}"
        done

    done <"${PACKAGES_FILE}"

}

generate_packages_apt_file() {
    dpkg-scanpackages "${PACKAGES_FOLDER}" /dev/null | gzip -9c >"${PACKAGES_FOLDER}/Packages.gz"
}

compress_folder() {
    tar -czvf "${COMPRESSED_FILE}" "${PACKAGES_FOLDER}"
}

main() {
    mkdir -p "${PACKAGES_FOLDER}"
    cd "${PACKAGES_FOLDER}"

    install_dependencies
    generate_packages_list
    download_packages
    generate_packages_apt_file
    compress_folder
}

main
