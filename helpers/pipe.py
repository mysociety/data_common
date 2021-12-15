"""
Quick function for functional pipe-like syntax
But in a more pythonic way

The current values can be referred to in a partial func by using 'Pipe.value'. 

"""
from typing import Callable, Any, Optional, Tuple, Iterator
from functools import partial
from itertools import product, chain
import itertools


class PartialLibrary:
    def __init__(self, library):
        self._library = library

    def __getattribute__(self, name):
        if name in ["_library"]:
            return super().__getattribute__(name)
        else:
            func = getattr(self._library, name)
            return partial(partial, func, Pipe.value)


class PipeEnd:
    pass


class PipeValue:
    pass


def amend_partial(pfunc: Callable, value: Any) -> Tuple[Callable, str]:
    """
    If partial args refers to PipeValue,
    substitute for current value moving through the pipe
    """

    kw_values = pfunc.keywords.values()
    self_contained = PipeValue in pfunc.args or PipeValue in kw_values
    if self_contained is False:
        return pfunc, self_contained

    args = [x if x != PipeValue else value for x in pfunc.args]
    kwargs = {k: (v if v != PipeValue else value) for k, v in pfunc.keywords.items()}

    return partial(pfunc.func, *args, **kwargs), self_contained


class PipeStart:
    def __init__(self, value):
        self.value = value
        self.operations = []

    def handle_operation(self, func: Callable) -> Any:
        """
        pass value into next function
        """
        self_contained = False
        if isinstance(func, partial):
            func, self_contained = amend_partial(func, self.value)
        if self_contained:
            return func()
        else:
            return func(self.value)

    def __add__(self, other: Callable) -> "PipeStart":
        """
        new functions are passed through the add operation
        to a PipeStart
        """
        if isinstance(other, PipeEnd):
            return self.value
        self.value = self.handle_operation(other)
        return self


def map_and_chain(func, *iterables, chain=False):
    result = map(func, *iterables)
    if chain:
        result = itertools.chain(*result)
    return result


class Pipe:
    """
    Starting value, then a list of functions to pass the result through.
    Current value can be referred as Pipe.value if it can't be passed through one value in a partial.
    """

    start = PipeStart
    value = PipeValue
    end = PipeEnd()
    partial = partial
    itertools = PartialLibrary(itertools)

    @staticmethod
    def map(func, chain=False):
        return partial(map_and_chain, func, chain=chain)

    @staticmethod
    def chain(values):
        return chain(*values)

    def __new__(cls, *args, **kwargs) -> Any:
        value = Pipe.start(args[0])
        for operation in args[1:]:
            value += operation
        return value + Pipe.end


class Pipeline:
    """
    chain together the transformations
    for a pipe
    but does not have an initial value

    Can then be called with the value

    """

    def __init__(self, *items):
        self.items = items

    def __call__(self, value: Any) -> Any:
        return Pipe(value, *self.items)


def iter_format(str_source: str, *args, **kwargs) -> Iterator[str]:
    """
    like str.format but args past in should be iterable
    Iterate through the full combination of formats provided.
    """
    if args:
        kwargs |= {x: y for x, y in enumerate(args)}
    keys = list(kwargs.keys())
    parameters = product(*[kwargs[key] for key in keys])

    def label_parameters(x):
        return {x: y for x, y in zip(keys, x)}

    def pos_from_keyword(p):
        x = 0
        while x in p:
            yield p[x]
            x += 1

    for p in parameters:
        kw_parameters = label_parameters(p)
        pos_parameters = Pipe(kw_parameters, pos_from_keyword, list)
        yield str_source.format(*pos_parameters, **kw_parameters)
