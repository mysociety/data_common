import socket
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/script.projects",
]

url_template = "https://docs.google.com/document/d/{0}/edit"


class DriveIntegration:
    def __init__(self, data):
        self.creds = Credentials.from_authorized_user_info(data, SCOPES)
        self.api = build("drive", "v3", credentials=self.creds)

    def upload_file(self, file_name, file_path, folder_id, drive_id):

        body = {
            "name": file_name,
            "driveID": drive_id,
            "parents": [folder_id],
            "mimeType": "application/vnd.google-apps.document",
        }

        # Now create the media file upload object and tell it what file to upload,
        # in this case 'test.html'
        media = MediaFileUpload(
            file_path,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        # Now we're doing the actual post, creating a new file of the uploaded type
        uploaded = (
            self.api.files()
            .create(body=body, media_body=media, supportsTeamDrives=True)
            .execute()
        )
        url = url_template.format(uploaded["id"])
        return url


class ScriptIntergration:
    def __init__(self, data):
        self.creds = Credentials.from_authorized_user_info(data, SCOPES)
        socket.setdefaulttimeout(600)  # set timeout to 10 minutes
        self.api = build("script", "v1", credentials=self.creds)

    def get_function(self, script_id, function_name):
        def inner(*args):
            request = {"function": function_name, "parameters": list(args)}
            response = (
                self.api.scripts().run(body=request, scriptId=script_id).execute()
            )

            return response

        return inner


def trigger_log_in_flow(settings: dict):

    # If there are no (valid) credentials available, let the user log in.
    data = settings["GOOGLE_APP_JSON"]
    flow = InstalledAppFlow.from_client_config(data, SCOPES)
    creds = flow.run_local_server(port=0)
    json_creds = creds.to_json()
    print(f"GOOGLE_CLIENT_JSON={json_creds}")
    raise ValueError("Add the following last line printed to the .env")


def test_settings(settings):
    """
    Test we have all the bits we need to connect to the api
    """

    if "GOOGLE_APP_JSON" not in settings or settings["GOOGLE_APP_JSON"] == "":
        raise ValueError(
            "Missing GOOGLE_APP_JSON settings. See the notebook setup page in the wiki for the correct settings."
        )

    if "GOOGLE_CLIENT_JSON" not in settings or settings["GOOGLE_CLIENT_JSON"] == "":
        trigger_log_in_flow(settings)
