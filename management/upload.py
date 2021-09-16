from notebook_helper.apis.google_api import (
    DriveIntegration, ScriptIntergration, test_settings)
from .settings import settings


def upload_file(file_name, file_path, g_folder_id, g_drive_id):
    """
    upload file to Climate Emergency metrics folder
    """
    api = DriveIntegration(settings["GOOGLE_CLIENT_JSON"])

    print("uploading document to drive")
    url = api.upload_file(file_name, file_path, g_folder_id, g_drive_id)
    print(url)
    return url


def format_document(url):
    """
    Apply google sheets formatter to URL
    """
    api = ScriptIntergration(settings["GOOGLE_CLIENT_JSON"])
    script_id = "AKfycbwjKpOgzKaDHahyn-7If0LzMhaNfMTTsiHf6nvgL2gaaVsgI_VvuZjHJWAzRaehENLX"
    func = api.get_function(script_id, "formatWordURL")
    print("formatting document, this may take a few minutes")
    v = func(url)
    print(v)


def g_drive_upload_and_format(file_name, file_path, g_folder_id, g_drive_id):
    test_settings(settings)
    url = upload_file(file_name, file_path, g_folder_id, g_drive_id)
    format_document(url)
