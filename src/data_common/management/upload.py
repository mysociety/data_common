from data_common.apis.google_api import (
    DriveIntegration,
    ScriptIntergration,
    test_settings,
)
from .settings import settings
from typing import Any
from pathlib import Path


def upload_file(
    file_name: str, file_path: str | Path, g_folder_id: str, g_drive_id: str
):
    """
    upload file to google drive
    """
    api = DriveIntegration(settings["GOOGLE_CLIENT_JSON"])

    print("uploading document to drive")
    url = api.upload_file(file_name, file_path, g_folder_id, g_drive_id)
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


def g_drive_upload_and_format(
    file_name: str, file_path: str | Path, g_folder_id: str, g_drive_id: str
):
    test_settings(settings)
    url = upload_file(file_name, file_path, g_folder_id, g_drive_id)
    format_document(url)
