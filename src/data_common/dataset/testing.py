from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple


class DatasetTestResult(NamedTuple):
    """
    Describe one isolated invocation of a dataset repository's tests.
    """

    paths: tuple[Path, ...]
    returncode: int

    @property
    def passed(self) -> bool:
        """
        Return whether pytest completed successfully.
        """
        return self.returncode == 0


def run_dataset_tests(
    test_paths: Iterable[Path],
    *,
    repo_root: Path,
    quiet: bool = False,
) -> DatasetTestResult:
    """
    Run dataset-owned tests in an isolated pytest subprocess.

    Running pytest outside the library process avoids sharing imported test
    modules, plugins, and global pytest state with callers.
    """
    paths = tuple(path.resolve() for path in test_paths)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--quiet",
        *(str(path) for path in paths),
    ]
    output = subprocess.DEVNULL if quiet else None
    completed = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        stdout=output,
        stderr=subprocess.STDOUT if quiet else None,
    )
    return DatasetTestResult(paths=paths, returncode=completed.returncode)
