import logging
import os
import re
import requests
import sys
from typing import Tuple

DOCKERFILE = "Dockerfile"
GO_MOD_FILE = "go.mod"
GO_MOD_GO_VERSION_REGEX = r"go\s\d+.*"
GO_VERSIONS_URL = "https://go.dev/dl/?mode=json"
GOMOD_GO_VERSION_UPDATER_ACTION_LOGGING_LEVEL = os.getenv(
    "GOMOD_GO_VERSION_UPDATER_ACTION_LOGGING_LEVEL", logging.INFO
)


def determine_whether_go_version_in_go_mod_file_contains_patch_version() -> (
    Tuple[str, bool]
):
    patch = False
    version = ""

    if not os.path.exists(GO_MOD_FILE):
        print(f"Error: The file '{GO_MOD_FILE}' does not exist.")
        return "", False

    try:
        with open(GO_MOD_FILE, "r") as file:
            major, minor, patch = "", "", ""
            content = file.read()
            go_version = re.search(r"go\s(\d+)\.(\d+)\.?(\d+)?", content)
            if go_version is None:
                raise ValueError(
                    f"no golang version defined in file: {GO_MOD_FILE}"
                )
            major, minor, patch = (
                go_version.group(1),
                go_version.group(2),
                go_version.group(3),
            )
            logging.debug(
                f"major: {major}, minor: {minor} and patch: {patch} found in go.mod"
            )
            version = f"{major}.{minor}"
            if patch:
                version = f"{major}.{minor}.{patch}"
                patch = True
            logging.debug(f"go version: {version}. Patch: {patch}")
            logging.debug(
                f"current golang version that is defined in the go.mod: {version}"
            )
            return version, patch
    except Exception as e:
        raise ValueError(f"an error occurred: {e}")


def get_latest_go_version():
    major, minor, patch = "", "", ""
    try:
        response = requests.get(GO_VERSIONS_URL)
        response.raise_for_status()
        data = response.json()
        latest_version = data[0]["version"]
        logging.debug(
            f"latest go version: {latest_version} according to: {GO_VERSIONS_URL}"
        )
        version_regex = re.compile(r"go(\d+)\.(\d+)\.(\d+)")
        match_data = version_regex.match(latest_version)
        if match_data:
            major, minor, patch = match_data.groups()
        else:
            logging.info("No version found in the input string.")
    except requests.exceptions.RequestException as e:
        logging.info(f"Error fetching data: {GO_VERSIONS_URL} {e}")
        sys.exit(1)
    logging.debug(f"latest go major: {major}, minor: {minor} and {patch}")
    return major, minor, patch


def regex_replace_go_version_in_go_mod_file(
    current_version: str, replacement: str
):
    try:
        with open(GO_MOD_FILE, "r") as file:
            content = file.read()
        modified_content = re.sub(
            GO_MOD_GO_VERSION_REGEX, f"go {replacement}", content
        )
        with open(GO_MOD_FILE, "w") as file:
            file.write(modified_content)
        logging.info(
            f"bump golang version in go.mod file from {current_version} to {replacement}"
        )
    except FileNotFoundError:
        logging.info(f"file not found: {GO_MOD_FILE}")
    except Exception as e:
        logging.info(f"an error occurred: {e}")


def configure_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def bump_version_in_dockerfile(new_major: str, new_minor: str, new_patch: str):
    if not os.path.exists(DOCKERFILE):
        print(f"Error: The file '{DOCKERFILE}' does not exist.")
        return "", False

    try:
        three_digit_pattern = re.compile(r"FROM\sgolang:(\d+\.\d+\.\d+)")
        two_digit_pattern = re.compile(r"FROM\sgolang:(\d+\.\d+)")

        try:
            with open(DOCKERFILE, "r") as file:
                lines = file.readlines()
        except FileNotFoundError:
            print(f"Error: The file '{DOCKERFILE}' was not found.")
            return
        except IOError as e:
            print(f"Error reading file '{DOCKERFILE}': {e}")
            return

        updated_lines = []

        for line in lines:
            match_three_digit = three_digit_pattern.search(line)
            if match_three_digit:
                version = match_three_digit.group(1)
                new_version = f"{new_major}.{new_minor}.{new_patch}"
                updated_line = line.replace(version, new_version)
                updated_lines.append(updated_line)
                continue

            match_two_digit = two_digit_pattern.search(line)
            if match_two_digit:
                version = match_two_digit.group(1)
                new_version = f"{new_major}.{new_minor}"
                updated_line = line.replace(version, new_version)
                updated_lines.append(updated_line)
                continue

            updated_lines.append(line)
        try:
            with open(DOCKERFILE, "w") as file:
                file.writelines(updated_lines)
        except IOError as e:
            print(f"Error writing to file '{DOCKERFILE}': {e}")
            return
        print(f"Updated content written to {DOCKERFILE}.")
    except Exception as e:
        raise ValueError(f"an error occurred: {e}")


def main():
    configure_logging(GOMOD_GO_VERSION_UPDATER_ACTION_LOGGING_LEVEL)
    latest_major, latest_minor, latest_patch = get_latest_go_version()
    current_version, patch = (
        determine_whether_go_version_in_go_mod_file_contains_patch_version()
    )
    if patch:
        regex_replace_go_version_in_go_mod_file(
            current_version, f"{latest_major}.{latest_minor}.{latest_patch}"
        )
        bump_version_in_dockerfile(latest_major, latest_minor, latest_patch)
        return
    regex_replace_go_version_in_go_mod_file(
        current_version, f"{latest_major}.{latest_minor}"
    )
    bump_version_in_dockerfile(latest_major, latest_minor, latest_patch)


if __name__ == "__main__":
    main()
