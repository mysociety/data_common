from enum import Enum, EnumMeta, auto
from typing import Any


class TypedEnumType(EnumMeta):
    def __new__(cls, name: str, bases: Any, dct: dict[str, Any]):
        # Go through the type annotations
        annotations = dct.get("__annotations__", {})
        for attr, typ in annotations.items():
            # if typ is annotated, extract the metadata and use that as
            # the function to create the attribute
            if typ in [str, "str"] and attr not in dct:
                # Assign the auto class to the attribute
                dct[attr] = auto()
        for key, value in dct.items():
            if isinstance(value, str):
                if key.lower() == value.lower() and value != value.lower():
                    raise ValueError(f"value {value} is not lowercase version of {key}")
        # Create the class as normal
        return super().__new__(cls, name, bases, dct)  # type: ignore


class StrEnum(str, Enum, metaclass=TypedEnumType):
    """
    Basically members are effectively strings for most purposes.
    the `auto()` shortcut can also be triggered using the str typehint.
    """

    def __new__(cls, *values: str):
        if len(values) > 3:
            raise TypeError("too many arguments for str(): %r" % (values,))
        if len(values) == 1:
            # it must be a string
            if not isinstance(values[0], str):  # type: ignore
                raise TypeError("%r is not a string" % (values[0],))
        if len(values) >= 2:
            # check that encoding argument is a string
            if not isinstance(values[1], str):  # type: ignore
                raise TypeError("encoding must be a string, not %r" % (values[1],))
        if len(values) == 3:
            # check that errors argument is a string
            if not isinstance(values[2], str):  # type: ignore
                raise TypeError("errors must be a string, not %r" % (values[2]))
        value = str(*values)
        member = str.__new__(cls, value)
        member._value_ = value
        return member

    def __str__(self) -> str:
        return str(self.value)

    @staticmethod
    def _generate_next_value_(
        name: str, start: int, count: int, last_values: list[Any]
    ) -> str:
        """
        Return the lower-cased version of the member name.
        """
        return name.lower()

    def __repr__(self) -> str:
        return str.__repr__(self.value)

    @classmethod
    def to_yaml(cls, representer: Any, node: Any):
        return representer.represent_scalar("tag:yaml.org,2002:str", str(node))
