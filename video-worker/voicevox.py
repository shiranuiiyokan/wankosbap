import os
from pathlib import Path
import requests

BASE_URL = os.getenv("VOICEVOX_URL", "http://127.0.0.1:50021")
DEFAULT_SPEED = float(os.getenv("VOICEVOX_SPEED", "1.50"))

def wait_until_ready(timeout=180):
    response = requests.get(f"{BASE_URL}/version", timeout=timeout)
    response.raise_for_status()
    return response.text

def resolve_speaker_id():
    explicit = os.getenv("VOICEVOX_SPEAKER_ID")
    if explicit:
        return int(explicit)
    response = requests.get(f"{BASE_URL}/speakers", timeout=30)
    response.raise_for_status()
    for speaker in response.json():
        if speaker.get("name") == os.getenv("VOICEVOX_SPEAKER_NAME", "ずんだもん"):
            wanted = os.getenv("VOICEVOX_STYLE_NAME", "ノーマル")
            return int(next((s["id"] for s in speaker["styles"] if s.get("name") == wanted), speaker["styles"][0]["id"]))
    raise RuntimeError("VOICEVOX speaker not found")

def synthesize(text: str, output_path: Path, speaker_id=None):
    speaker_id = speaker_id if speaker_id is not None else resolve_speaker_id()
    q = requests.post(f"{BASE_URL}/audio_query", params={"text": text, "speaker": speaker_id}, timeout=60)
    q.raise_for_status()
    query = q.json()
    query["speedScale"] = float(os.getenv("VOICEVOX_SPEED", str(DEFAULT_SPEED)))
    query["outputSamplingRate"] = 48000
    s = requests.post(f"{BASE_URL}/synthesis", params={"speaker": speaker_id}, json=query, timeout=180)
    s.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(s.content)
    return output_path
