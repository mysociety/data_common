from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal, NamedTuple, Self

from pydantic import BaseModel, ConfigDict, Field


class FormatOption(NamedTuple):
    """
    Pair a download format name with its enabled state.
    """

    name: str
    enabled: bool


class FormatSettings(BaseModel):
    """
    Configure the resource formats generated for a dataset.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    csv: bool = True
    parquet: bool = True
    geojson: bool = False
    gpkg: bool = False

    def options(self) -> tuple[FormatOption, ...]:
        """
        Return declared and extension format flags as typed pairs.
        """
        values = {
            "csv": self.csv,
            "parquet": self.parquet,
            "geojson": self.geojson,
            "gpkg": self.gpkg,
        }
        values.update(
            {name: bool(enabled) for name, enabled in (self.model_extra or {}).items()}
        )
        return tuple(FormatOption(name, enabled) for name, enabled in values.items())


class CompositeConfiguration(BaseModel):
    """
    Validate unresolved composite configuration from datapackage YAML.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    include: list[str] | Literal["all"] = "all"
    exclude: list[str] | Literal["none", "None"] = "none"
    modify: dict[str, str | dict[str, str]] = Field(default_factory=dict)
    render: bool = True

    def resolve(self, resource_names: Iterable[str]) -> CompositeOptions:
        """
        Resolve the YAML shortcuts into concrete resource name lists.
        """
        include = list(resource_names) if self.include == "all" else list(self.include)
        exclude = [] if isinstance(self.exclude, str) else list(self.exclude)
        return CompositeOptions(
            include=include,
            exclude=exclude,
            modify={
                resource: operations
                for resource, operations in self.modify.items()
                if isinstance(operations, dict)
            },
            render=self.render,
        )


class CompositeOptions(BaseModel):
    """
    Hold resolved composite options used by package builders.
    """

    model_config = ConfigDict(frozen=True)

    include: list[str]
    exclude: list[str]
    modify: dict[str, dict[str, str]] = Field(default_factory=dict)
    render: bool = True


class CompositeSettings(BaseModel):
    """
    Configure all supported composite dataset formats.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    xlsx: CompositeConfiguration = Field(default_factory=CompositeConfiguration)
    json_format: CompositeConfiguration = Field(
        default_factory=CompositeConfiguration,
        alias="json",
    )
    sqlite: CompositeConfiguration = Field(default_factory=CompositeConfiguration)

    def for_format(
        self,
        data_format: str,
    ) -> CompositeConfiguration:
        """
        Return configuration for a supported composite format.
        """
        if data_format == "json":
            return self.json_format
        if data_format == "xlsx":
            return self.xlsx
        if data_format == "sqlite":
            return self.sqlite
        return CompositeConfiguration()


class DownloadOptions(BaseModel):
    """
    Configure dataset-specific download form behaviour.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    gate: str = "default"
    survey: str = "default"
    header_text: str = "default"


class DatasetteSettings(BaseModel):
    """
    Configure the information link displayed by Datasette.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    about: str = "Info & Downloads"
    about_url: str = ""

    def with_default_url(self, url: str) -> DatasetteSettings:
        """
        Supply the dataset site URL when no explicit URL is configured.
        """
        return self.model_copy(
            update={"about": self.about, "about_url": self.about_url or url}
        )


class DataPackageExtras(BaseModel):
    """
    Represent the application-specific values in datapackage custom metadata.

    Unknown fields are retained so repositories can add metadata without losing
    it when the package version is updated or publication JSON is generated.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    build: str = ""
    tests: list[str] = Field(default_factory=list)
    dataset_order: int = 999
    is_geodata: bool = False
    formats: FormatSettings = Field(default_factory=FormatSettings)
    composite: CompositeSettings = Field(default_factory=CompositeSettings)
    download_options: DownloadOptions = Field(default_factory=DownloadOptions)
    change_log: dict[str, str] = Field(default_factory=dict)
    datasette: DatasetteSettings = Field(default_factory=DatasetteSettings)

    @classmethod
    def from_datapackage(cls, datapackage: Mapping[str, Any]) -> Self:
        """
        Parse custom metadata from a full datapackage mapping.
        """
        return cls.model_validate(datapackage.get("custom") or {})

    def with_change(self, version: str, message: str) -> DataPackageExtras:
        """
        Return extras containing an additional version change message.
        """
        change_log = dict(self.change_log)
        change_log[version] = message
        return self.model_copy(update={"change_log": change_log})

    def for_publication(self, dataset_url: str) -> DataPackageExtras:
        """
        Return extras with publication defaults made explicit.
        """
        return self.model_copy(
            update={
                "dataset_order": self.dataset_order,
                "datasette": self.datasette.with_default_url(dataset_url),
            }
        )

    def as_datapackage_value(self) -> dict[str, Any]:
        """
        Return YAML/JSON-compatible custom metadata without implicit defaults.
        """
        return self.model_dump(by_alias=True, exclude_unset=True)
