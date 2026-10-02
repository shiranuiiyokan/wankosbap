from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from drive_client import build_drive_service, download_file, download_folder_recursive, find_named_child, list_child_folders, storage_quota
from manifest import normalize_manifest
from qc import disk_guard
from renderer import render_job

ROOT = Path(__file__).parent
WORK_ROOT = ROOT / "work"
OUTPUT_ROOT = ROOT / "output"

CATEGORY_ENV = {
    "dog": "SCHEDULED_DOG_FOLDER_ID",
    "mbti": "SCHEDULED_MBTI_FOLDER_ID",
    "cat_other": "SCHEDULED_CAT_FOLDER_ID",
    "news": "SCHEDULED_NEWS_FOLDER_ID",
    "long": "SCHEDULED_LONG_FOLDER_ID",
}
MANIFEST_NAMES = ("manifest.json", "job.json", "metadata.json")


def _bool(name: str, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _find_manifest(job_dir: Path):
    for name in MANIFEST_NAMES:
        candidate = job_dir / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("manifest.json/job.json/metadata.json missing")


def _pick_folder(service, parent_id, project_filter: str | None):
    folders = list_child_folders(service, parent_id, 100)
    if project_filter:
        folders = [x for x in folders if project_filter in x.get("name", "")]
    if not folders:
        raise RuntimeError("no matching scheduled folder")
    pick = os.getenv("V2_PICK", "oldest").strip().lower()
    return folders[-1] if pick == "latest" else folders[0]


def main():
    category = os.getenv("V2_CATEGORY", "dog").strip()
    if category not in CATEGORY_ENV:
        raise ValueError(f"unsupported category: {category}")
    parent_id = os.getenv(CATEGORY_ENV[category], "").strip()
    if not parent_id:
        raise RuntimeError(f"missing {CATEGORY_ENV[category]}")

    strict_qc = _bool("V2_STRICT_QC", False)
    preflight_only = _bool("V2_PREFLIGHT_ONLY", True)
    project_filter = os.getenv("V2_PROJECT_FILTER", "").strip() or None

    WORK_ROOT.mkdir(exist_ok=True)
    guard = disk_guard(ROOT, float(os.getenv("V2_MIN_FREE_GB", "4")))
    print("V2_DISK_GUARD=" + json.dumps(guard.to_dict(), ensure_ascii=False), flush=True)
    if not guard.ok:
        raise SystemExit(2)

    service = build_drive_service()
    print("V2_DRIVE_QUOTA=" + json.dumps(storage_quota(service), ensure_ascii=False), flush=True)
    folder = _pick_folder(service, parent_id, project_filter)

    job_dir = WORK_ROOT / folder["id"]
    out_dir = OUTPUT_ROOT / folder["id"]
    shutil.rmtree(job_dir, ignore_errors=True)
    shutil.rmtree(out_dir, ignore_errors=True)

    try:
        if preflight_only:
            manifest_item = find_named_child(service, folder["id"], MANIFEST_NAMES)
            if not manifest_item:
                raise FileNotFoundError("manifest.json/job.json/metadata.json missing")
            manifest_path = job_dir / manifest_item["name"]
            download_file(service, manifest_item["id"], manifest_path)
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            job = normalize_manifest(raw, category, job_dir, validate_images=False)
        else:
            download_folder_recursive(service, folder["id"], job_dir)
            manifest_path = _find_manifest(job_dir)
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            job = normalize_manifest(raw, category, job_dir, validate_images=True)
        result = render_job(job, job_dir, out_dir, strict_qc=strict_qc, preflight_only=preflight_only)
        result.update({
            "source_folder": folder["name"],
            "shadow_mode": True,
            "drive_write": False,
            "youtube_upload": False,
        })
        print("V2_SHADOW_RESULT=" + json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        if _bool("V2_KEEP_LOCAL", False):
            print(f"V2_KEEP_LOCAL work={job_dir} output={out_dir}", flush=True)
        else:
            shutil.rmtree(job_dir, ignore_errors=True)
            shutil.rmtree(out_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
