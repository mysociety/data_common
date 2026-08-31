import pytest

from data_common.dataset.version_management import (
    bump_version,
    is_valid_semver,
    map_versions_to_latest_major_minor,
    parse_semver,
    semver_is_higher,
)


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("1.2.3", True),
        ("1.2.3-rc.1", True),
        ("1.2.3+build.4", True),
        ("1.2", False),
        ("01.2.3", False),
    ],
)
def test_semver_validation(value: str, valid: bool) -> None:
    assert is_valid_semver(value) is valid
    assert (parse_semver(value) is not None) is valid


@pytest.mark.parametrize(
    ("current", "part", "expected"),
    [
        ("1.2.3", "major", "2.0.0"),
        ("1.2.3", "minor", "1.3.0"),
        ("1.2.3", "patch", "1.2.4"),
    ],
)
def test_bump_version(current: str, part: str, expected: str) -> None:
    assert bump_version(current, part) == expected


def test_version_comparison_and_aliases() -> None:
    assert semver_is_higher("1.9.9", "2.0.0")
    assert not semver_is_higher("2.0.0", "1.9.9")
    assert map_versions_to_latest_major_minor(
        ["1.0.0", "1.0.2", "1.1.0", "2.0.0", "3.0.0-rc.1"]
    ) == {
        "1.0": "1.0.2",
        "1": "1.1.0",
        "1.1": "1.1.0",
        "2.0": "2.0.0",
        "2": "2.0.0",
        "latest": "2.0.0",
    }
