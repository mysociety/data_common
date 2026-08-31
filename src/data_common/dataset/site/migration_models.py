from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class MigrationDownloadSettings(BaseModel):
    """
    Hold download settings translated from the legacy Jekyll configuration.
    """

    model_config = ConfigDict(frozen=True)

    gate: str = "soft"
    survey: str = ""
    form_header: str = "Can you help us by telling us more about yourself?"
    show_code_examples: bool = True
    show_subscription: bool = True


class MigrationAnalysisSettings(BaseModel):
    """
    Hold analysis settings added during repository migration.
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    bundle_dir: str = "_render/site/analysis"


class MigrationSiteSettings(BaseModel):
    """
    Hold the complete site configuration generated during migration.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    description: str
    intro: str
    base_url: str
    canonical_url: str
    source_url: str
    output_dir: str = "_site"
    accent_colour: str = "#4faded"
    downloads: MigrationDownloadSettings
    analysis: MigrationAnalysisSettings = Field(
        default_factory=MigrationAnalysisSettings,
    )


class LegacyDownloadValues(BaseModel):
    """
    Validate legacy download fields that have direct Flask-site equivalents.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    download_gate_type: str | None = None
    download_survey: str | None = None
    download_form_header: str | None = None


class LegacyDefaultScope(BaseModel):
    """
    Validate a legacy Jekyll default scope.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    type: str = ""


class LegacyDefault(BaseModel):
    """
    Validate one legacy Jekyll defaults entry.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    scope: LegacyDefaultScope = Field(default_factory=LegacyDefaultScope)
    values: LegacyDownloadValues = Field(default_factory=LegacyDownloadValues)


class LegacyJekyllConfiguration(BaseModel):
    """
    Validate the legacy Jekyll settings used by migration.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    title: str | None = None
    description: str | None = None
    baseurl: str = ""
    url: str = ""
    defaults: list[LegacyDefault] = Field(default_factory=list)


class MigrationReport(BaseModel):
    """
    Record proposed or applied repository migration changes.
    """

    repo_root: Path
    actions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    applied: bool = False

    @property
    def changed(self) -> bool:
        """
        Return whether the migration found any work to perform.
        """
        return bool(self.actions)
