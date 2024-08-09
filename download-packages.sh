#!/bin/bash

PACKAGES_FOLDER="${1:-updates}"
COMPRESSED_FILE="${2:-updates.tar.gz}"
CURR_FOLDER="$(pwd)"
PACKAGES_FILE="${CURR_FOLDER}/packages.list"

install_dependencies() {
    apt update
    DEBIAN_FRONTEND=noninteractive apt install -y \
        dpkg-dev \
        mawk \
        gzip \
        tar
}

generate_packages_list() {
    # List all installed packages
    dpkg-query -W -f='${Status} ${package}=${version}\n' | grep "^install ok installed" | awk '{print $4}' >"${PACKAGES_FILE}"
    cat "${PACKAGES_FILE}"
}

download_packages() {
    cd "${PACKAGES_FOLDER}"
    while IFS= read -r package; do
        package_name=$(echo "${package}" | cut -d '=' -f 1)
        package_version=$(echo "${package}" | cut -d '=' -f 2)

        # Handle already downloaded packages
        downloaded_file=$(find . -name "${package_name}_*.deb")
        if [ -f "${downloaded_file}" ]; then
            # TODO: this verification won't work with files that have encoded some characters in the name
            # eg: version is '1:5.8.1+dfsg-2' but filename has '1%3a5.8.1+dfsg-2'
            downloaded_file_has_correct_version=$(echo "${downloaded_file}" | grep "${package_version}" || true)
            if [ -n "${downloaded_file_has_correct_version}" ]; then
                echo "Package ${package_name} already downloaded with version ${package_version}: ${downloaded_file}. Skipping..."
                continue
            else
                echo "Older version for package ${package_name} found: ${downloaded_file}. Removing..."
                rm -f "${downloaded_file}"
            fi
        fi

        echo "Downloading ${package}..."
        DOWNLOAD_CMD="apt download ${package} &>/dev/null"
        CMD_OUTPUT=$(eval "${DOWNLOAD_CMD}")
        # Retry on failure
        if [ $? -ne 0 ]; then
            echo "Failed to download package ${package}. Retrying with latest version..."
            sleep 1

            echo "Downloading ${package_name}..."
            DOWNLOAD_CMD="apt download ${package_name} &>/dev/null"
            CMD_OUTPUT=$(eval "${DOWNLOAD_CMD}")
            if [ $? -ne 0 ]; then
                echo "Failed to download package ${package_name}. Skipping..."
            fi
        fi

    done <"${PACKAGES_FILE}"
    cd "${CURR_FOLDER}"
}

generate_packages_apt_file() {
    cd "${PACKAGES_FOLDER}"
    rm -rf Packages Release Packages.gz
    apt-ftparchive packages . > Packages
    apt-ftparchive \
        -o APT::FTPArchive::Release::Origin="pi-top-offline" \
        -o APT::FTPArchive::Release::Label="pi-top Offline Repository" \
        -o APT::FTPArchive::Release::Suite="offline" \
        -o APT::FTPArchive::Release::Architectures="armhf arm64 amd64 all" \
        -o APT::FTPArchive::Release::Components="main" \
        -o APT::FTPArchive::Release::Description="pi-top offline repository" \
        release . > Release

    # Change Release file date to the past to avoid errors on devices
    # where date is not synchronized
    sed -i "s|Date: .*|Date: $(date -R -u -d '2000-01-01')|g" Release
}

compress_folder() {
    cd "${CURR_FOLDER}"
    rm -rf "${COMPRESSED_FILE}"
    tar -czvf "${COMPRESSED_FILE}" "${PACKAGES_FOLDER}"
}

main() {
    mkdir -p "${PACKAGES_FOLDER}"
    install_dependencies
    generate_packages_list
    download_packages
    generate_packages_apt_file
    compress_folder
}

main
