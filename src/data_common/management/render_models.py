from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel


class RenderOptions(BaseModel):
    """
    Configure execution and source visibility for notebook rendering.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    rerun: bool = True
    hide_input: bool = True


class UploadConfiguration(
    RootModel[dict[str, dict[str, Any] | None]],
):
    """
    Hold upload target configuration keyed by exporter name.
    """


class DocumentDefinition(BaseModel):
    """
    Validate one configured notebook document.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    title: str
    slug: str
    notebooks: list[str]
    options: RenderOptions = Field(default_factory=RenderOptions)
    context: dict[str, list[str]] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    upload: UploadConfiguration = Field(
        default_factory=lambda: UploadConfiguration({}),
    )
    meta: bool = False
    group: str | None = None
    extends: str | None = None


class RenderedDocument(BaseModel):
    """
    Hold the context-sensitive title, slug, and parameter values.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    slug: str
    parameters: dict[str, Any]
