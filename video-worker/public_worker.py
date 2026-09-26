import io
import json
import os
import shutil
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from googleapiclient.http import MediaIoBaseUpload

from drive_client import build_drive_service, download_file
from scheduled_renderer import render_scheduled_job, audio_duration
from voicevox import synthesize, wait_until_ready
from youtube_upload import upload_video

ROOT = Path(__file__).parent
WORK_ROOT = ROOT / "work"
OUTPUT_ROOT = ROOT / "output"
JST = timezone(timedelta(hours=9))

CATEGORY_ENV = {
    "dog": "SCHEDULED_DOG_FOLDER_ID",
    "mbti": "SCHEDULED_MBTI_FOLDER_ID",
    "cat_other": "SCHEDULED_CAT_FOLDER_ID",
    "long": "SCHEDULED_LONG_FOLDER_ID",
}
DEFAULT_LIMITS = {"dog": 3, "mbti": 3, "cat_other": 3, "long": 1}
DEFAULT_SLOTS = {
    "dog": ["09:30", "13:00", "19:00"],
    "mbti": ["08:00", "15:30", "21:00"],
    "cat_other": ["10:30", "17:00", "22:00"],
    "long": ["20:30"],
}
MANIFEST_NAMES = ("manifest.json", "job.json", "metadata.json")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class InvalidAssetError(RuntimeError):
    """Permanent scheduled-asset structure error; quarantine instead of retrying forever."""



def read_json(path: Path, default=None):
    default = {} if default is None else default
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def required_env(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def category_folders():
    return {cat: os.getenv(env, "").strip() for cat, env in CATEGORY_ENV.items() if os.getenv(env, "").strip()}


def list_child_folders(service, parent_id, limit=100):
    q = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    resp = service.files().list(
        q=q,
        pageSize=limit,
        orderBy="createdTime",
        fields="files(id,name,createdTime,modifiedTime)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    return resp.get("files", [])


def list_children(service, folder_id, limit=1000):
    q = f"'{folder_id}' in parents and trashed=false"
    resp = service.files().list(
        q=q,
        pageSize=limit,
        orderBy="name",
        fields="files(id,name,mimeType,size,createdTime,modifiedTime)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    return resp.get("files", [])


def download_folder_recursive(service, folder_id, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    for item in list_children(service, folder_id):
        target = destination / item["name"]
        if item["mimeType"] == "application/vnd.google-apps.folder":
            download_folder_recursive(service, item["id"], target)
        else:
            download_file(service, item["id"], target)


def move_folder(service, folder_id, from_parent, to_parent):
    service.files().update(
        fileId=folder_id,
        addParents=to_parent,
        removeParents=from_parent,
        fields="id,parents",
        supportsAllDrives=True,
    ).execute()


def rename_folder(service, folder_id, new_name):
    service.files().update(
        fileId=folder_id,
        body={"name": new_name},
        fields="id,name",
        supportsAllDrives=True,
    ).execute()


def _extract_uploaded_video_id(folder_name):
    marker = "__YT_"
    if marker not in folder_name:
        return None
    return folder_name.split(marker, 1)[1].split("__", 1)[0].strip() or None


def upsert_json(service, folder_id, filename, data):
    payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    media = MediaIoBaseUpload(io.BytesIO(payload), mimetype="application/json", resumable=False)
    q = f"'{folder_id}' in parents and name='{filename}' and trashed=false"
    found = service.files().list(
        q=q,
        pageSize=10,
        fields="files(id,name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute().get("files", [])
    if found:
        return service.files().update(
            fileId=found[0]["id"],
            media_body=media,
            fields="id,name",
            supportsAllDrives=True,
        ).execute()
    return service.files().create(
        body={"name": filename, "parents": [folder_id]},
        media_body=media,
        fields="id,name",
        supportsAllDrives=True,
    ).execute()


def upload_binary(service, folder_id, filename, path: Path, mimetype="video/mp4"):
    media = MediaIoBaseUpload(path.open("rb"), mimetype=mimetype, resumable=True)
    q = f"'{folder_id}' in parents and name='{filename}' and trashed=false"
    found = service.files().list(
        q=q,
        pageSize=10,
        fields="files(id,name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute().get("files", [])
    if found:
        return service.files().update(
            fileId=found[0]["id"],
            media_body=media,
            fields="id,name",
            supportsAllDrives=True,
        ).execute()
    return service.files().create(
        body={"name": filename, "parents": [folder_id]},
        media_body=media,
        fields="id,name",
        supportsAllDrives=True,
    ).execute()


def find_child_by_name(service, folder_id, filename):
    q = f"'{folder_id}' in parents and name='{filename}' and trashed=false"
    files = service.files().list(
        q=q,
        pageSize=10,
        fields="files(id,name,mimeType,size)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute().get("files", [])
    return files[0] if files else None


def find_manifest(job_dir: Path):
    for name in MANIFEST_NAMES:
        path = job_dir / name
        if path.is_file():
            return path
    return None


def _scene_images(job_dir: Path):
    return sorted(
        p.name for p in job_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS and p.name.lower() != "cta.png"
    )


def _slots_for(category):
    env_name = {
        "dog": "DOG_PUBLISH_SLOTS",
        "mbti": "MBTI_PUBLISH_SLOTS",
        "cat_other": "CAT_PUBLISH_SLOTS",
        "long": "LONG_PUBLISH_SLOTS",
    }[category]
    raw = os.getenv(env_name, "").strip()
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else DEFAULT_SLOTS[category]


def fallback_publish_at(category, index, now=None):
    now = now or datetime.now(JST)
    days_ahead = max(0, int(os.getenv("PUBLISH_DAYS_AHEAD", "1")))
    start_date = (now + timedelta(days=days_ahead)).date()
    candidates = []
    for day_offset in range(8):
        target_date = start_date + timedelta(days=day_offset)
        for slot in _slots_for(category):
            clock = datetime.strptime(slot, "%H:%M").time()
            candidate = datetime.combine(target_date, clock, JST)
            if candidate > now + timedelta(minutes=10):
                candidates.append(candidate)
        if len(candidates) > index:
            break
    if not candidates:
        raise ValueError(f"no future publish slot available for {category}")
    return candidates[index % len(candidates)].isoformat()


def resolve_publish_at(manifest, category, publish_index):
    raw = manifest.get("publish_at")
    if raw:
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=JST)
            if parsed.astimezone(JST) > datetime.now(JST) + timedelta(minutes=10):
                return parsed.isoformat()
            print(f"STALE publish_at={raw}; using next future slot for {category}", flush=True)
        except Exception:
            print(f"INVALID publish_at={raw}; using next future slot for {category}", flush=True)
    return fallback_publish_at(category, publish_index)


def normalize_job(manifest, category, folder_name, job_dir, publish_index):
    project_id = manifest.get("project_id") or manifest.get("企画ID") or manifest.get("job_id") or folder_name
    series = str(manifest.get("series") or category).lower()
    title = manifest.get("title") or manifest.get("youtube", {}).get("title") or folder_name
    description = manifest.get("description") or manifest.get("youtube", {}).get("description") or ""

    scenes = manifest.get("scenes")
    if not scenes:
        images = manifest.get("images") or _scene_images(job_dir)
        narrations = manifest.get("narrations") or []
        scenes = []
        for i, image in enumerate(images):
            scene = {"image": image}
            if i < len(narrations):
                scene["narration"] = narrations[i]
            scenes.append(scene)
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("manifest must contain scenes or usable images")

    narration_enabled = bool(manifest.get("narration_enabled", True))
    normalized = []
    for i, scene in enumerate(scenes, start=1):
        if isinstance(scene, str):
            scene = {"image": scene}
        image = scene.get("image")
        if not image:
            raise ValueError(f"scene {i} missing image")
        if not (job_dir / image).is_file():
            raise ValueError(f"scene {i} image not found: {image}")
        narration = scene.get("narration") or scene.get("voice") or ""
        if narration_enabled and not narration:
            raise ValueError(f"scene {i} missing narration")
        item = {"image": image, "narration": narration}
        reading = scene.get("narration_reading") or scene.get("voice_reading")
        if reading:
            item["narration_reading"] = str(reading).strip()
        overlay = scene.get("overlay_text") or scene.get("on_screen_text")
        if overlay:
            item["overlay_text"] = str(overlay).strip()
        if scene.get("duration") is not None:
            item["duration"] = scene["duration"]
        normalized.append(item)

    youtube = dict(manifest.get("youtube") or {})
    if os.getenv("PUBLISH_IMMEDIATELY", "false").lower() in {"1", "true", "yes"}:
        youtube["publish_immediately"] = True
        youtube["schedule_publish"] = False
    youtube.setdefault("title", title)
    youtube.setdefault("description", description)
    youtube.setdefault("tags", manifest.get("tags", []))
    youtube.setdefault("category_id", "15")
    youtube.setdefault("made_for_kids", False)
    youtube.setdefault("contains_synthetic_media", True)
    youtube.setdefault("schedule_publish", True)

    video = dict(manifest.get("video") or {})
    if category == "long":
        video.setdefault("width", 1920)
        video.setdefault("height", 1080)
    else:
        video.setdefault("width", 1080)
        video.setdefault("height", 1920)

    job = {
        "job_id": str(project_id),
        "project_id": str(project_id),
        "series": series,
        "category": category,
        "title": title,
        "publish_at": resolve_publish_at(manifest, category, publish_index),
        "youtube": youtube,
        "video": video,
        "voice": dict(manifest.get("voice") or {}),
        "scenes": normalized,
        "narration_enabled": narration_enabled,
        "append_common_cta": manifest.get("append_common_cta", category != "long"),
    }
    if manifest.get("fixed_scene_durations"):
        job["fixed_scene_durations"] = True
    return job


def voice_speed(job):
    voice = job.get("voice") or {}
    if job.get("category") == "long":
        if voice.get("speed") is not None:
            return str(voice["speed"])
        return os.getenv("LONG_VOICE_SPEED", "1.25")

    # Keep Shorts brisk even when older manifests still contain speed=1.50.
    target = float(os.getenv("SHORTS_VOICE_SPEED", "1.65"))
    if voice.get("speed") is not None:
        try:
            target = max(target, float(voice["speed"]))
        except (TypeError, ValueError):
            pass
    return str(target)


def category_limits():
    return {
        "dog": int(os.getenv("DOG_JOB_LIMIT", "3")),
        "mbti": int(os.getenv("MBTI_JOB_LIMIT", "3")),
        "cat_other": int(os.getenv("CAT_JOB_LIMIT", "3")),
        "long": int(os.getenv("LONG_JOB_LIMIT", "1")),
    }


def process_one(service, category, source_parent, folder, publish_index, dry_run=False):
    job_dir = WORK_ROOT / category / folder["id"]
    out_dir = OUTPUT_ROOT / category / folder["id"]
    shutil.rmtree(job_dir, ignore_errors=True)
    shutil.rmtree(out_dir, ignore_errors=True)

    uploaded_video_id = _extract_uploaded_video_id(folder["name"])
    if uploaded_video_id:
        move_folder(service, folder["id"], source_parent, required_env("SCHEDULED_DONE_FOLDER_ID"))
        print(f"RECOVER move only: {folder['name']} video_id={uploaded_video_id}", flush=True)
        return {"status": "done", "video_id": uploaded_video_id}

    if find_child_by_name(service, folder["id"], "youtube_result.json"):
        move_folder(service, folder["id"], source_parent, required_env("SCHEDULED_DONE_FOLDER_ID"))
        print(f"RECOVER legacy upload marker: {folder['name']}", flush=True)
        return {"status": "done"}

    download_folder_recursive(service, folder["id"], job_dir)
    manifest_path = find_manifest(job_dir)
    if not manifest_path:
        if os.getenv("SKIP_INCOMPLETE", "false").lower() in {"1", "true", "yes"}:
            print(f"WAIT incomplete asset: {category}/{folder['name']} manifest missing", flush=True)
            return {"status": "waiting"}
        raise InvalidAssetError("manifest.json/job.json/metadata.json is missing")

    job = normalize_job(read_json(manifest_path, {}), category, folder["name"], job_dir, publish_index)
    old_speed = os.environ.get("VOICEVOX_SPEED")
    os.environ["VOICEVOX_SPEED"] = voice_speed(job)
    try:
        wait_until_ready()
        video = render_scheduled_job(job, job_dir, out_dir, synthesize)
        rendered_duration = audio_duration(video)
        if category == "long":
            min_long_seconds = max(60, int(os.getenv("MIN_LONG_SECONDS", "900")))
            if rendered_duration < min_long_seconds:
                raise RuntimeError(
                    f"long quality gate failed: rendered_duration={rendered_duration:.1f}s "
                    f"< minimum={min_long_seconds}s project_id={job['project_id']}"
                )
        if dry_run:
            result = {
                "project_id": job["project_id"],
                "category": category,
                "rendered_at": datetime.now(JST).isoformat(),
                "filename": video.name,
                "rendered_duration_seconds": round(rendered_duration, 1),
            }
            print("PUBLIC_RENDER_DRY_RUN=" + json.dumps(result, ensure_ascii=False), flush=True)
            return {"status": "rendered", **result}

        required_env("YOUTUBE_CLIENT_ID")
        required_env("YOUTUBE_CLIENT_SECRET")
        required_env("YOUTUBE_REFRESH_TOKEN")
        result = upload_video(video, job)
        result.update({
            "project_id": job["project_id"],
            "category": category,
            "uploaded_at": datetime.now(JST).isoformat(),
        })

        # Persist idempotency without creating a new Drive file. Renaming an
        # existing shared folder consumes no service-account storage quota.
        marker_name = f"{folder['name']}__YT_{result['video_id']}"
        rename_folder(service, folder["id"], marker_name)

        # Only after the upload is durably marked do we move the source folder.
        move_folder(service, folder["id"], source_parent, required_env("SCHEDULED_DONE_FOLDER_ID"))
        print("PUBLIC_UPLOAD_RESULT=" + json.dumps(result, ensure_ascii=False), flush=True)
        return {"status": "done", **result}
    finally:
        if old_speed is None:
            os.environ.pop("VOICEVOX_SPEED", None)
        else:
            os.environ["VOICEVOX_SPEED"] = old_speed


def main():
    dry_run = os.getenv("DRY_RUN", "false").lower() in {"1", "true", "yes"}
    service = build_drive_service()
    folders = category_folders()
    if not folders:
        raise RuntimeError("no scheduled category folder IDs configured")
    required_env("SCHEDULED_DONE_FOLDER_ID")
    required_env("SCHEDULED_ERROR_FOLDER_ID")
    limits = category_limits()

    processed = 0
    failures = 0
    for category in ("dog", "mbti", "cat_other", "long"):
        source = folders.get(category)
        if not source:
            continue

        # Scan beyond the nominal limit so one malformed/stale folder cannot
        # consume a daily publish slot forever. Only successful jobs advance
        # publish_index, so later jobs fill the skipped slot (e.g. 17:00).
        available = list_child_folders(service, source, limit=max(50, limits[category] * 10))
        allowlist_raw = os.getenv("PROJECT_ID_ALLOWLIST", "").strip()
        if allowlist_raw:
            allowlist = [x.strip() for x in allowlist_raw.split(",") if x.strip()]
            available = [
                folder for folder in available
                if any(project_id in folder.get("name", "") for project_id in allowlist)
            ]
        category_processed = 0
        print(
            f"CATEGORY={category} available={len(available)} target={limits[category]}",
            flush=True,
        )

        for folder in available:
            if category_processed >= limits[category]:
                break
            try:
                result = process_one(
                    service,
                    category,
                    source,
                    folder,
                    category_processed,
                    dry_run=dry_run,
                )
                if result.get("status") in {"done", "rendered"}:
                    processed += 1
                    category_processed += 1
            except InvalidAssetError as exc:
                failures += 1
                print(
                    f"QUARANTINE {category}/{folder['name']}: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
                print(traceback.format_exc(limit=8), flush=True)
                if not dry_run:
                    move_folder(
                        service,
                        folder["id"],
                        source,
                        required_env("SCHEDULED_ERROR_FOLDER_ID"),
                    )
            except Exception as exc:
                failures += 1
                print(f"ERROR {category}/{folder['name']}: {type(exc).__name__}: {exc}", flush=True)
                print(traceback.format_exc(limit=8), flush=True)

    summary = {"processed": processed, "failures": failures, "dry_run": dry_run, "limits": limits}
    print("PUBLIC_PRODUCTION_SUMMARY=" + json.dumps(summary, ensure_ascii=False), flush=True)
    if failures and processed == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
