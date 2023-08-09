from typing import (
    get_args,
    Any,
    Type,
    TypeVar,
    Callable,
    Generic,
    ParamSpec,
    get_type_hints,
)

from inspect import signature

T = TypeVar("T")
P = ParamSpec("P")


class ValidationTest(Generic[T]):
    root_type: Type[T]
    test: Callable[[T], Any]
    error: Callable[[T], Exception]

    def __init__(
        self,
        root_type: Type[T],
        test: Callable[[T], Any],
        error: Callable[[T], Exception],
    ):
        self.root_type = root_type
        self.test = test
        self.error = error

    def __call__(self, *args, **kwargs):
        return self.test(*args, **kwargs)


def inspect_function(func):
    sig = signature(func)
    parameters = sig.parameters
    args = []
    kwargs = {}

    for param_name, param in parameters.items():
        if param.default == param.empty:
            args.append(param_name)
        else:
            kwargs[param_name] = param.default

    return args, kwargs


def merge_args_kwargs(func, *args, **kwargs):
    expected_args, expected_kwargs = inspect_function(func)

    if len(args) > len(expected_args):
        raise ValueError(
            f"Function expects {len(expected_args)} positional arguments, but {len(args)} were provided."
        )

    merged_kwargs = expected_kwargs.copy()

    for i, arg in enumerate(args):
        merged_kwargs[expected_args[i]] = arg

    merged_kwargs.update(kwargs)

    return merged_kwargs


def enforce_types(func: Callable[P, T]) -> Callable[P, T]:
    """
    This lets us move some basic validation items into the type hint structure
    """
    type_hints = get_type_hints(func, include_extras=True)
    expected_args, expected_kwargs = inspect_function(func)

    def wrapper(*args: P.args, **kwargs: P.kwargs):
        if len(args) > len(expected_args):
            raise ValueError(
                f"Function expects {len(expected_args)} positional arguments, but {len(args)} were provided."
            )

        merged_kwargs = expected_kwargs.copy()

        for i, arg in enumerate(args):
            merged_kwargs[expected_args[i]] = arg

        merged_kwargs.update(kwargs)

        for arg, type_ in type_hints.items():
            if arg == "return":
                continue
            parameter_value = merged_kwargs[arg]
            enforce_type(parameter_value, type_)
        value = func(*args, **kwargs)
        if "return" in type_hints:
            enforce_type(value, type_hints["return"])
        return value

    return wrapper


def enforce_type(object: T, annotated_type: Type[T]) -> None:
    meta_data = get_args(annotated_type)

    if not meta_data:
        if not isinstance(object, annotated_type):
            raise TypeError(f"Expected {annotated_type} but got {type(object)}")

    if meta_data:
        type_ = meta_data[0]

        if not isinstance(object, type_):
            raise TypeError(f"Expected {type_} but got {type(object)}")
        tests = meta_data[1:]

        for test in tests:
            if not test(object):
                raise test.error(object)
