from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ANALYSIS_SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class AnalysisBundleMetadata(BaseModel):
    """
    Configure the presentation of an exported notebook analysis.
    """

    model_config = ConfigDict(extra="allow")

    description: str = ""
    order: int = 999
    external_css: list[str] = Field(default_factory=list)
    external_js: list[str] = Field(default_factory=list)


class AnalysisBundleManifest(AnalysisBundleMetadata):
    """
    Describe the versioned JSON contract consumed by the dataset site.
    """

    schema_version: Literal[1] = 1
    kind: Literal["analysis"] = "analysis"
    slug: str = Field(pattern=ANALYSIS_SLUG_PATTERN)
    title: str
