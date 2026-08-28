"""Lightweight console entry points for optional data_common features."""


def _missing_extra(command: str, extra: str, error: ModuleNotFoundError) -> None:
    missing = error.name or "an optional dependency"
    raise SystemExit(
        f"The {command!r} command requires data-common[{extra}]; "
        f"missing module: {missing}."
    ) from error


def dataset() -> None:
    """Run the dataset publication CLI."""
    try:
        from data_common.dataset.__main__ import run
    except ModuleNotFoundError as error:
        _missing_extra("dataset", "dataset", error)
    run()


def notebook() -> None:
    """Run the notebook rendering CLI."""
    try:
        from data_common.notebookcli.__main__ import run
    except ModuleNotFoundError as error:
        _missing_extra("notebook", "render", error)
    run()
