import re


def map_versions_to_latest_major_minor(
    versions: list[str], include_latest: bool = False
) -> dict[str, str]:
    """
    Given a list of major,minor,patch semvers
    Produce a dictionary that maps from major and major.minor versions
    to the latest relevant full version
    """
    version_map = {}
    split_versions = [x.split(".") for x in versions]
    split_versions = [(int(x), int(y), int(z)) for x, y, z in split_versions]
    split_versions.sort()

    for major, minor, patch in split_versions:
        version_map[f"{major}.{minor}"] = f"{major}.{minor}.{patch}"
        version_map[f"{major}"] = f"{major}.{minor}.{patch}"
    version_map["latest"] = ".".join([str(x) for x in split_versions[-1]])
    return version_map


def is_valid_semver(semver: str) -> bool:
    """
    Returns True if the given string is a valid semver, False otherwise.
    """
    return parse_semver(semver) is not None


def parse_semver(version_string: str) -> None | dict[str, str]:
    """
    Parse a string and return a dictionary of its semver components.
    If the string is not a valid semver, return None.
    """
    semver_regex = re.compile(
        r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
    )
    match = semver_regex.match(version_string)
    if match is None:
        return None
    return match.groupdict()


def semver_is_higher(semver1: str, semver2: str) -> bool:
    """Returns True if semver2 is a higher version than semver1, False otherwise."""
    # parse semvers into dictionaries
    semver1_dict = parse_semver(semver1)
    semver2_dict = parse_semver(semver2)
    # if either semver is not valid, return False
    if semver1_dict is None or semver2_dict is None:
        return False
    # compare major versions
    if int(semver2_dict["major"]) > int(semver1_dict["major"]):
        return True
    # compare minor versions
    if int(semver2_dict["major"]) == int(semver1_dict["major"]) and int(
        semver2_dict["minor"]
    ) > int(semver1_dict["minor"]):
        return True
    # compare patch versions
    if (
        int(semver2_dict["major"]) == int(semver1_dict["major"])
        and int(semver2_dict["minor"]) == int(semver1_dict["minor"])
        and int(semver2_dict["patch"]) > int(semver1_dict["patch"])
    ):
        return True
    # otherwise, semver2 is not a higher version
    return False


def bump_version(semver: str, choice: str):
    """
    Given a semver string and a choice of major, minor, or patch,
    bumps the semver to the next version and correctly lower more
    minor versions.
    """
    # Parse the semver into parts
    parts = parse_semver(semver)

    if parts is None:
        raise ValueError(f"Invalid semvar {semver}")

    # Check if the given choice is a valid one
    if choice not in ["major", "minor", "patch"]:
        raise ValueError(f"Invalid choice: {choice}")

    # Bump the requested part
    parts[choice] = str(int(parts[choice]) + 1)

    # If we've bumped the major version, reset the minor and patch
    if choice == "major":
        parts["minor"] = "0"
        parts["patch"] = "0"

    # If we've bumped the minor version, reset the patch
    if choice == "minor":
        parts["patch"] = "0"

    # Join all the parts together and return
    return ".".join([parts["major"], parts["minor"], parts["patch"]])
