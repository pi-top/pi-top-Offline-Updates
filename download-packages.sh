#!/bin/bash

PACKAGES_FOLDER="packages"
PACKAGES_FILE="packages.list"
COMPRESSED_FILE="packages.tar.gz"
CURR_FOLDER="$(pwd)"

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
    dpkg-query -W -f='${Status} ${package}=${version}\n' | grep "^install ok installed" | awk '{print $4}' >"${PACKAGES_FOLDER}/${PACKAGES_FILE}"
    cat "${PACKAGES_FOLDER}/${PACKAGES_FILE}"
}

download_packages() {
    cd "${PACKAGES_FOLDER}"
    while IFS= read -r package; do
        package_name=$(echo "${package}" | cut -d '=' -f 1)
        package_version=$(echo "${package}" | cut -d '=' -f 2)

        # Handle already downloaded packages
        downloaded_file=$(find . -name "${package_name}_*.deb")
        if [ -f "${downloaded_file}" ]; then
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
        while [ $? -ne 0 ]; do
            echo "Error: ${CMD_OUTPUT}"
            echo "Failed to download packlage ${package}. Retrying..."
            sleep 1
            eval "${DOWNLOAD_CMD} || true" # TODO: remove '|| true'
        done
    done <"${PACKAGES_FILE}"
    cd "${CURR_FOLDER}"
}

generate_packages_apt_file() {
    cd "${CURR_FOLDER}"
    dpkg-scanpackages "${PACKAGES_FOLDER}" /dev/null | gzip -9c >"${PACKAGES_FOLDER}/Packages.gz"
}

compress_folder() {
    cd "${CURR_FOLDER}"
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
