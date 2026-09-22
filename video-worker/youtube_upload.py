import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import DEFAULT_CATEGORY_ID, YOUTUBE_UPLOAD_SCOPE

def build_youtube_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=[YOUTUBE_UPLOAD_SCOPE],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)

def upload_video(video_path: Path, job: dict):
    youtube = build_youtube_service()
    y = job.get("youtube", {})
    description = y.get("description", "")
    credit = os.getenv("VOICEVOX_CREDIT", "VOICEVOX:ずんだもん")
    if credit and credit not in description:
        description = description.rstrip() + f"\n\n音声: {credit}"
    publish_immediately = bool(y.get("publish_immediately", False))
    status = {
        "privacyStatus": "public" if publish_immediately else "private",
        "selfDeclaredMadeForKids": bool(y.get("made_for_kids", False)),
        "containsSyntheticMedia": bool(y.get("contains_synthetic_media", False)),
    }
    publish_at = job.get("publish_at")
    scheduled = bool(publish_at and y.get("schedule_publish", True))
    if scheduled:
        status["publishAt"] = publish_at
    body = {
        "snippet": {
            "title": (y.get("title") or job.get("title") or "Pet video")[:100],
            "description": description,
            "tags": y.get("tags", []),
            "categoryId": str(y.get("category_id", DEFAULT_CATEGORY_ID)),
            "defaultLanguage": y.get("default_language", "ja"),
        },
        "status": status,
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        progress, response = request.next_chunk()
        if progress:
            print(f"YouTube upload: {int(progress.progress() * 100)}%", flush=True)
    return {
        "video_id": response["id"],
        "youtube_url": f"https://www.youtube.com/watch?v={response['id']}",
        "publish_at": publish_at if scheduled else None,
        "privacy_status": "scheduled" if scheduled else response.get("status", {}).get("privacyStatus", status["privacyStatus"]),
    }
