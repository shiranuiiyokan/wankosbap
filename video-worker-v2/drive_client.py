import json
import os
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive"]


def build_drive_service():
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_child_folders(service, parent_id, limit=100):
    q = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    resp = service.files().list(
        q=q, pageSize=limit, orderBy="createdTime",
        fields="files(id,name,createdTime,modifiedTime)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    return resp.get("files", [])


def list_children(service, folder_id, limit=1000):
    q = f"'{folder_id}' in parents and trashed=false"
    resp = service.files().list(
        q=q, pageSize=limit, orderBy="name",
        fields="files(id,name,mimeType,size,createdTime,modifiedTime)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    return resp.get("files", [])


def download_file(service, file_id, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with destination.open("wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def download_folder_recursive(service, folder_id, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    for item in list_children(service, folder_id):
        target = destination / item["name"]
        if item["mimeType"] == "application/vnd.google-apps.folder":
            download_folder_recursive(service, item["id"], target)
        else:
            download_file(service, item["id"], target)


def storage_quota(service):
    try:
        return service.about().get(fields="storageQuota").execute().get("storageQuota") or {}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def find_named_child(service, folder_id, names):
    wanted = set(names)
    for item in list_children(service, folder_id):
        if item.get("name") in wanted and item.get("mimeType") != "application/vnd.google-apps.folder":
            return item
    return None
