from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import mkdtemp
from uuid import uuid4

from .schemas import AnalysisBundleManifest, AnalysisBundleMetadata
from .settings import SiteSettings


def replace_bundle_directory(staging: Path, destination: Path) -> None:
    """
    Replace an existing bundle directory while preserving rollback safety.

    The staging and destination directories must share a filesystem so their
    renames are atomic.
    """
    backup = destination.parent / f".{destination.name}.previous-{uuid4().hex}"
    if destination.exists():
        destination.rename(backup)
    try:
        staging.rename(destination)
    except Exception:
        if backup.exists():
            backup.rename(destination)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)


def publish_analysis_bundle(
    *,
    source_file: Path,
    resources_dir: Path,
    settings: SiteSettings,
    slug: str,
    title: str,
    metadata: AnalysisBundleMetadata | None = None,
) -> Path:
    """
    Publish notebook HTML and resources as a validated analysis bundle.

    The bundle is assembled completely before it replaces the previous
    version, preventing partial output when rendering fails.
    """
    metadata_values = metadata.model_dump() if metadata else {}
    manifest = AnalysisBundleManifest.model_validate(
        {
            **metadata_values,
            "schema_version": 1,
            "kind": "analysis",
            "slug": slug,
            "title": title,
        }
    )

    bundle_root = settings.analysis.bundle_dir.resolve()
    bundle_root.mkdir(parents=True, exist_ok=True)
    destination = (bundle_root / manifest.slug).resolve()
    if destination.parent != bundle_root:
        raise ValueError(f"Analysis bundle escapes configured directory: {destination}")

    staging = Path(mkdtemp(prefix=f".{manifest.slug}-", dir=bundle_root))
    try:
        body = source_file.read_text().replace(
            "_notebook_resources",
            "notebook_resources",
        )
        (staging / "body.html").write_text(body)
        (staging / "page.json").write_text(manifest.model_dump_json(indent=2) + "\n")

        if resources_dir.exists():
            shutil.copytree(
                resources_dir,
                staging / "notebook_resources",
                dirs_exist_ok=True,
            )
        replace_bundle_directory(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return destination
