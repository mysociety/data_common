# pyright: strict
from itertools import product
from typing import Any, Iterator


def iter_format(
    str_source: str, *args: Iterator[Any], **kwargs: Iterator[Any]
) -> Iterator[str]:
    """
    like str.format but args passed in should be iterable
    Iterate through the full combination of formats provided.
    """
    if args:
        kwargs |= {str(x): y for x, y in enumerate(args)}
    keys = list(kwargs.keys())
    parameters = product(*[kwargs[key] for key in keys])

    def label_parameters(parameter: tuple[Any]) -> dict[str, Any]:
        return {str(x): y for x, y in zip(keys, parameter)}

    def pos_from_keyword(p: dict[str, Any]) -> Iterator[str]:
        x = 0
        while str(x) in p:
            yield p[str(x)]
            x += 1

    for p in parameters:
        kw_parameters = label_parameters(p)  # type: ignore
        pos_parameters = list(pos_from_keyword(kw_parameters))
        yield str_source.format(*pos_parameters, **kw_parameters)
