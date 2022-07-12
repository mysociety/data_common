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


class DriveIntegration:
    def __init__(self, data):
        self.creds = Credentials.from_authorized_user_info(data, SCOPES)
        self.api = build("drive", "v3", credentials=self.creds)
        self.allowed_drives: dict[str, str] = {
            x["name"]: x["id"] for x in self.api.drives().list().execute()["drives"]
        }

    def expand_drive_id(self, drive_id: str) -> str:

        if drive_id in self.allowed_drives:
            drive_id = self.allowed_drives[drive_id]
        return drive_id

    def folder_id_from_path(self, drive_id: str, drive_path: str | Path) -> str:
        """
        Given a path and a drive_id, try and get the id of the specific folder
        """

        drive_id = self.expand_drive_id(drive_id)
        current_parent = drive_id
        file_id = None
        for p in Path(drive_path).parts:
            files = (
                self.api.files()
                .list(
                    corpora="drive",
                    driveId=drive_id,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    q=f"mimeType = 'application/vnd.google-apps.folder' and name = '{p}' and '{current_parent}' in parents",
                )
                .execute()
            )
            if len(files["files"]) == 0:
                raise ValueError(f"Folder part {p} not found.")
            if len(files["files"]) > 1:
                raise ValueError(f"Multiple folder {p} found.")

            file_id = files["files"][0]["id"]
            current_parent = file_id

        if file_id is None:
            raise ValueError(f"Couldn't resolve path: {drive_path}")

        return file_id

    def upload_file(
        self,
        file_path: str | Path,
        file_name: str | None = None,
        drive_name: str | None = None,
        folder_path: str | None = None,
        folder_id: str | None = None,
        drive_id: str | None = None,
    ):
        """
        Upload a file to a google drive folder

        You need file_path and (drive_name or drive_id) and (folder_path or folder_id)

        """

        file_path = Path(file_path)

        if file_path.suffix == ".docx":
            mimetype = "application/vnd.google-apps.document"
            upload_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            url_template = "https://docs.google.com/document/d/{0}/edit"
        elif file_path.suffix == ".csv":
            mimetype = "application/vnd.google-apps.spreadsheet"
            upload_type = "text/csv"
            url_template = "https://docs.google.com/spreadsheets/d/{0}/edit"
        elif file_path.suffix == ".xlsx":
            mimetype = "application/vnd.google-apps.spreadsheet"
            upload_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            url_template = "https://docs.google.com/spreadsheets/d/{0}/edit"
        else:
            raise ValueError(f"Don't have a good handler for {file_path.suffix}")

        if not file_name:
            file_name = file_path.stem

        if drive_name and drive_id:
            raise ValueError("Only specify one of drive_name and drive_id")
        if folder_id and folder_path:
            raise ValueError("Only specify one of folder_path and folder_id")

        if drive_name:
            drive_id = self.expand_drive_id(drive_name)
        if not drive_id:
            raise ValueError("No drive_id specified")
        if folder_path:
            folder_id = self.folder_id_from_path(drive_id, folder_path)
        if not folder_id:
            raise ValueError("No folder_id specified")

        body = {
            "name": file_name,
            "driveID": drive_id,
            "parents": [folder_id],
            "mimeType": mimetype,
        }

        file_path = str(file_path)
        # Now create the media file upload object and tell it what file to upload,
        # in this case 'test.html'
        media = MediaFileUpload(
            file_path,
            mimetype=upload_type,
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
    def __init__(self, data: dict):
        self.creds = Credentials.from_authorized_user_info(data, SCOPES)
        socket.setdefaulttimeout(600)  # set timeout to 10 minutes
        self.api = build("script", "v1", credentials=self.creds)

    def get_function(self, script_id: str, function_name: str):
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
    if not data:
        raise ValueError("GOOGLE_APP_JSON not defined")
    flow = InstalledAppFlow.from_client_config(data, SCOPES)
    creds = flow.run_local_server(port=0)
    json_creds = creds.to_json()
    print(f"GOOGLE_CLIENT_JSON={json_creds}")
    raise ValueError("Add the following last line printed to the .env")


def test_settings(settings: dict):
    """
    Test we have all the bits we need to connect to the api
    """

    if "GOOGLE_APP_JSON" not in settings or settings["GOOGLE_APP_JSON"] == "":
        raise ValueError(
            "Missing GOOGLE_APP_JSON settings. See the notebook setup page in the wiki for the correct settings."
        )

    if "GOOGLE_CLIENT_JSON" not in settings or settings["GOOGLE_CLIENT_JSON"] == "":
        trigger_log_in_flow(settings)
