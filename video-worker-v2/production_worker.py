from __future__ import annotations

import json
import os
import shutil
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from drive_client import build_drive_service, download_folder_recursive, list_child_folders, storage_quota
from manifest import normalize_manifest
from qc import disk_guard
from renderer import render_job
from youtube_upload import upload_video

ROOT = Path(__file__).parent
WORK_ROOT = ROOT / "work-production"
OUTPUT_ROOT = ROOT / "output-production"
JST = timezone(timedelta(hours=9))

CATEGORY_ENV = {
    "dog": "SCHEDULED_DOG_FOLDER_ID",
    "mbti": "SCHEDULED_MBTI_FOLDER_ID",
    "cat_other": "SCHEDULED_CAT_FOLDER_ID",
    "news": "SCHEDULED_NEWS_FOLDER_ID",
    "long": "SCHEDULED_LONG_FOLDER_ID",
}
DEFAULT_LIMITS = {"dog": 3, "mbti": 3, "cat_other": 3, "news": 2, "long": 1}
DEFAULT_SLOTS = {
    "dog": ["09:30", "13:00", "19:00"],
    "mbti": ["08:00", "15:30", "21:00"],
    "cat_other": ["10:30", "17:00", "22:00"],
    "news": ["14:30", "19:30", "21:30"],
    "long": ["20:30"],
}
MANIFEST_NAMES = ("manifest.json", "job.json", "metadata.json")


class QCWait(RuntimeError):
    pass


class InvalidAsset(RuntimeError):
    pass


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def env_bool(name: str, default=False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def find_manifest(job_dir: Path) -> Path:
    for name in MANIFEST_NAMES:
        path = job_dir / name
        if path.is_file():
            return path
    raise InvalidAsset("manifest missing")


def move_folder(service, folder_id: str, source: str, destination: str):
    service.files().update(
        fileId=folder_id,
        addParents=destination,
        removeParents=source,
        fields="id,parents",
        supportsAllDrives=True,
    ).execute()


def rename_folder(service, folder_id: str, name: str):
    service.files().update(
        fileId=folder_id,
        body={"name": name},
        fields="id,name",
        supportsAllDrives=True,
    ).execute()


def uploaded_marker(name: str):
    if "__YT_" not in name:
        return None
    return name.split("__YT_", 1)[1].split("__", 1)[0].strip() or None


def clean_base_name(name: str) -> str:
    return name.split("__V2_HOLD_", 1)[0]


def mark_qc_hold(service, folder: dict, code: str):
    base = clean_base_name(folder["name"])
    marker = f"{base}__V2_HOLD_{code}"
    if marker != folder["name"]:
        rename_folder(service, folder["id"], marker)


def slots_for(category: str) -> list[str]:
    raw = os.getenv(f"{category.upper()}_PUBLISH_SLOTS_V2", "").strip()
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else DEFAULT_SLOTS[category]


def fallback_publish_at(category: str, index: int) -> str:
    now = datetime.now(JST)
    cutoff = min(23, max(0, int(os.getenv("PUBLISH_DAY_CUTOFF_HOUR", "21"))))
    start = now.date() + timedelta(days=1 if now.hour >= cutoff else 0)
    candidates = []
    for day_offset in range(8):
        day = start + timedelta(days=day_offset)
        for slot in slots_for(category):
            clock = datetime.strptime(slot, "%H:%M").time()
            candidate = datetime.combine(day, clock, JST)
            if candidate > now + timedelta(minutes=10):
                candidates.append(candidate)
        if len(candidates) > index:
            return candidates[index].isoformat()
    raise RuntimeError(f"no future publish slot for {category}")


def apply_publish_metadata(job: dict, category: str, publish_index: int):
    youtube = dict(job.get("youtube") or {})
    youtube.setdefault("title", job.get("title"))
    youtube.setdefault("description", job.get("description", ""))
    youtube.setdefault("category_id", "15")
    youtube.setdefault("made_for_kids", False)
    youtube.setdefault("contains_synthetic_media", True)
    youtube.setdefault("schedule_publish", True)
    job["youtube"] = youtube

    raw = youtube.get("publish_at") or job.get("publish_at")
    if raw:
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=JST)
            if parsed.astimezone(JST) > datetime.now(JST) + timedelta(minutes=10):
                job["publish_at"] = parsed.isoformat()
                return
        except Exception:
            pass
    job["publish_at"] = fallback_publish_at(category, publish_index)


def category_limits() -> dict[str, int]:
    return {
        "dog": int(os.getenv("DOG_JOB_LIMIT_V2", "3")),
        "mbti": int(os.getenv("MBTI_JOB_LIMIT_V2", "3")),
        "cat_other": int(os.getenv("CAT_JOB_LIMIT_V2", "3")),
        "news": int(os.getenv("NEWS_JOB_LIMIT_V2", "2")),
        "long": int(os.getenv("LONG_JOB_LIMIT_V2", "1")),
    }


def render_strict(job: dict, job_dir: Path, out_dir: Path):
    # render_job synthesizes the continuous audio first and applies QC before any
    # visual encoding. A QC failure therefore avoids the expensive video render
    # without synthesizing the narration twice.
    try:
        return render_job(job, job_dir, out_dir, strict_qc=True, preflight_only=False)
    except RuntimeError as exc:
        message = str(exc)
        if "unresolved pronunciation risk:" in message:
            raise QCWait("PRON:" + message) from exc
        if " narration " in message and "target" in message:
            raise QCWait("DURATION:" + message) from exc
        raise


def process_one(service, category: str, source: str, folder: dict,
                publish_index: int, publish_enabled: bool):
    job_dir = WORK_ROOT / category / folder["id"]
    out_dir = OUTPUT_ROOT / category / folder["id"]
    shutil.rmtree(job_dir, ignore_errors=True)
    shutil.rmtree(out_dir, ignore_errors=True)

    existing = uploaded_marker(folder["name"])
    if existing:
        if publish_enabled:
            move_folder(service, folder["id"], source, required_env("SCHEDULED_DONE_FOLDER_ID"))
        return {"status": "done", "video_id": existing, "recovered": True}

    try:
        download_folder_recursive(service, folder["id"], job_dir)
        manifest_path = find_manifest(job_dir)
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        job = normalize_manifest(raw, category, job_dir, validate_images=True)
        apply_publish_metadata(job, category, publish_index)
        result = render_strict(job, job_dir, out_dir)

        if not publish_enabled:
            print("V2_PRODUCTION_DRY_RESULT=" + json.dumps(result, ensure_ascii=False), flush=True)
            return {"status": "rendered", **result}

        uploaded = upload_video(Path(result["video_path"]), job, result["speaker"])
        base = clean_base_name(folder["name"])
        rename_folder(service, folder["id"], f"{base}__YT_{uploaded['video_id']}")
        move_folder(service, folder["id"], source, required_env("SCHEDULED_DONE_FOLDER_ID"))
        uploaded.update({"project_id": job["project_id"], "category": category})
        print("V2_UPLOAD_RESULT=" + json.dumps(uploaded, ensure_ascii=False), flush=True)
        return {"status": "done", **uploaded}
    except QCWait as exc:
        code = "PRON" if str(exc).startswith("PRON:") else "DURATION"
        if publish_enabled:
            mark_qc_hold(service, folder, code)
        raise
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)


def main():
    publish_enabled = env_bool("V2_PUBLISH_ENABLED", False)
    if publish_enabled and os.getenv("V2_ACTIVATION_TOKEN", "") != "I_UNDERSTAND_V2_PUBLISHES":
        raise RuntimeError("v2 publishing is locked; activation token missing")

    guard = disk_guard(ROOT, float(os.getenv("V2_MIN_FREE_GB", "4")))
    print("V2_DISK_GUARD=" + json.dumps(guard.to_dict(), ensure_ascii=False), flush=True)
    if not guard.ok:
        raise SystemExit(2)

    service = build_drive_service()
    print("V2_DRIVE_QUOTA=" + json.dumps(storage_quota(service), ensure_ascii=False), flush=True)
    limits = category_limits()
    max_jobs = min(20, max(1, int(os.getenv("V2_MAX_UPLOADS_PER_RUN", "12"))))

    allow = os.getenv("CATEGORY_ALLOWLIST", "").strip()
    categories = ["dog", "mbti", "cat_other", "news", "long"]
    if allow:
        allowed = {x.strip() for x in allow.split(",") if x.strip()}
        categories = [x for x in categories if x in allowed]

    processed = 0
    waits = 0
    failures = 0

    for category in categories:
        if processed >= max_jobs:
            break
        parent = os.getenv(CATEGORY_ENV[category], "").strip()
        if not parent:
            continue

        target = min(limits[category], max_jobs - processed)
        folders = list_child_folders(service, parent, limit=max(30, target * 10))
        category_done = 0

        for folder in folders:
            if category_done >= target or processed >= max_jobs:
                break
            try:
                result = process_one(service, category, parent, folder, category_done, publish_enabled)
                if result.get("status") in {"done", "rendered"}:
                    processed += 1
                    category_done += 1
            except QCWait as exc:
                waits += 1
                print(f"V2_QC_WAIT {category}/{folder['name']}: {exc}", flush=True)
            except InvalidAsset as exc:
                failures += 1
                print(f"V2_INVALID_ASSET {category}/{folder['name']}: {exc}", flush=True)
                if publish_enabled:
                    move_folder(service, folder["id"], parent, required_env("SCHEDULED_ERROR_FOLDER_ID"))
            except Exception as exc:
                failures += 1
                print(f"V2_ERROR {category}/{folder['name']}: {type(exc).__name__}: {exc}", flush=True)
                print(traceback.format_exc(limit=8), flush=True)

    summary = {
        "processed": processed,
        "qc_waits": waits,
        "failures": failures,
        "publish_enabled": publish_enabled,
        "max_jobs": max_jobs,
    }
    print("V2_PRODUCTION_SUMMARY=" + json.dumps(summary, ensure_ascii=False), flush=True)
    if failures and processed == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
