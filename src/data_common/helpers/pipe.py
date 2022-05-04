from typing import Iterator
from itertools import product


def iter_format(str_source: str, *args, **kwargs) -> Iterator[str]:
    """
    like str.format but args past in should be iterable
    Iterate through the full combination of formats provided.
    """
    if args:
        kwargs |= {str(x): y for x, y in enumerate(args)}
    keys = list(kwargs.keys())
    parameters = product(*[kwargs[key] for key in keys])

    def label_parameters(x):
        return {str(x): y for x, y in zip(keys, x)}

    def pos_from_keyword(p):
        x = 0
        while x in p:
            yield p[x]
            x += 1

    for p in parameters:
        kw_parameters = label_parameters(p)
        pos_parameters = list(pos_from_keyword(kw_parameters))
        yield str_source.format(*pos_parameters, **kw_parameters)
