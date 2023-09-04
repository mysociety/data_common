from __future__ import annotations

from typing import Any, NamedTuple, Union
from urllib.parse import ParseResult, urlparse

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema
from typing_extensions import Self


class NetLoc(NamedTuple):
    username: str
    password: str
    hostname: str
    port: str

    @classmethod
    def from_parse_result(cls, parse_result: ParseResult):
        username, password = parse_result._userinfo  # type: ignore
        hostname, port = parse_result._hostinfo  # type: ignore
        return cls(username, password, hostname, port)

    def construct_netloc(self) -> str:
        base = self.hostname
        if self.port:
            base += ":" + self.port
        if self.username:
            if self.password:
                base = self.username + ":" + self.password + "@" + base
            else:
                base = self.username + "@" + base
        return base

    def __str__(self):
        return ":".join(self)


class UrlHandler:
    def __str__(self):
        return self._urlparse.geturl()

    def __init__(
        self,
        url: str,
    ):
        self._urlparse = urlparse(url)
        if self.scheme == "":
            self._urlparse = urlparse("https://" + url)
        self._netloc = NetLoc.from_parse_result(self._urlparse)

    def update(
        self,
        scheme: str = "",
        path: str = "",
        params: str = "",
        query: str = "",
        fragment: str = "",
        hostname: str = "",
        port: str = "",
        username: str = "",
        password: str = "",
    ) -> Self:
        new = self.__class__(self._urlparse.geturl())

        if scheme:
            new.scheme = scheme
        if path:
            new.path = path
        if params:
            new.params = params
        if query:
            new.query = query
        if fragment:
            new.fragment = fragment
        if scheme:
            new.scheme = scheme
        if hostname:
            new.hostname = hostname
        if port:
            new.port = port
        if username:
            new.username = username
        if password:
            new.password = password

        return new

    @property
    def scheme(self):
        return self._urlparse.scheme

    @property
    def path(self):
        return self._urlparse.path

    @property
    def params(self):
        return self._urlparse.params

    @property
    def query(self):
        return self._urlparse.query

    @property
    def fragment(self):
        return self._urlparse.fragment

    @property
    def username(self):
        return self._netloc.username

    @property
    def password(self):
        return self._netloc.password

    @property
    def hostname(self):
        return self._netloc.hostname

    @property
    def port(self):
        return self._netloc.port

    @scheme.setter
    def scheme(self, value: str):
        self._urlparse = self._urlparse._replace(scheme=value)

    @path.setter
    def path(self, value: str):
        self._urlparse = self._urlparse._replace(path=value)

    @params.setter
    def params(self, value: str):
        self._urlparse = self._urlparse._replace(params=value)

    @query.setter
    def query(self, value: str):
        self._urlparse = self._urlparse._replace(query=value)

    @fragment.setter
    def fragment(self, value: str):
        self._urlparse = self._urlparse._replace(fragment=value)

    @username.setter
    def username(self, value: str):
        self._netloc = self._netloc._replace(username=value)
        self._urlparse = self._urlparse._replace(netloc=self._netloc.construct_netloc())

    @password.setter
    def password(self, value: str):
        self._netloc = self._netloc._replace(password=value)
        self._urlparse = self._urlparse._replace(netloc=self._netloc.construct_netloc())

    @hostname.setter
    def hostname(self, value: str):
        self._netloc = self._netloc._replace(hostname=value)
        self._urlparse = self._urlparse._replace(netloc=self._netloc.construct_netloc())

    @port.setter
    def port(self, value: str | int):
        if isinstance(value, int):
            value = str(value)
        self._netloc = self._netloc._replace(port=value)
        self._urlparse = self._urlparse._replace(netloc=self._netloc.construct_netloc())

    def __truediv__(self, other: str) -> Self:
        new_url = self._urlparse._replace(path=self._urlparse.path + "/" + other)
        return self.__class__(new_url.geturl())


class Url(UrlHandler, str):
    """
    URL class that's pretending to be a string.

    Can access and set all the attributes of a URL, e.g.:
    url = Url("https://www.example.com")
    url.port = 8080
    url.path = "/path/to/resource"

    And this will modify this object in place.

    To return a new object - use the update method.

    Preferred way of adding paths to URLs is to use the / operator, e.g.:
    Url("https://www.example.com") / "path" / "to" / "resource"

    Using the strings + operator will revert back
    to being a normal string for compatibility.
    """

    def __new__(cls, url_string: str):
        return str.__new__(cls, url_string)

    def __init__(self, url_string: str):
        UrlHandler.__init__(self, url_string)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(cls, handler(str))


UrlLike = Union[str, Url]
