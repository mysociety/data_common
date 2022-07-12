from data_common.apis.google_api import (
    DriveIntegration,
    ScriptIntergration,
    test_settings,
)
from .settings import settings
from typing import Any
from pathlib import Path

from typing import ParamSpec


def upload_file(
    file_path: str | Path,
    file_name: str | None = None,
    drive_name: str | None = None,
    folder_path: str | None = None,
    folder_id: str | None = None,
    drive_id: str | None = None,
):
    """
    upload file to Google drive
    """
    api = DriveIntegration(settings["GOOGLE_CLIENT_JSON"])
    print("uploading document to drive")
    url = api.upload_file(
        file_path=file_path,
        file_name=file_name,
        drive_name=drive_name,
        folder_path=folder_path,
        folder_id=folder_id,
        drive_id=drive_id,
    )
    print(url)
    return url


def format_document(url: str):
    """
    Apply google sheets formatter to URL
    """
    api = ScriptIntergration(settings["GOOGLE_CLIENT_JSON"])
    script_id = (
        "AKfycbwjKpOgzKaDHahyn-7If0LzMhaNfMTTsiHf6nvgL2gaaVsgI_VvuZjHJWAzRaehENLX"
    )
    func = api.get_function(script_id, "formatWordURL")
    print("formatting document, this may take a few minutes")
    v: Any = func(url)
    print(v)


P = ParamSpec("P")


def g_drive_upload_and_format(
    file_path: str | Path,
    file_name: str | None = None,
    drive_name: str | None = None,
    folder_path: str | None = None,
    folder_id: str | None = None,
    drive_id: str | None = None,
):
    """
    Upload a file and then run the document formatter
    """
    test_settings(settings)
    url = upload_file(
        file_path=file_path,
        file_name=file_name,
        drive_name=drive_name,
        folder_path=folder_path,
        folder_id=folder_id,
        drive_id=drive_id,
    )
    format_document(url)
