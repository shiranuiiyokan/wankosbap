from __future__ import annotations

import hashlib
import os
from pathlib import Path
import requests

BASE_URL = os.getenv("VOICEVOX_URL", "http://127.0.0.1:50021")
DEFAULT_ROTATION = [
    "ずんだもん:ノーマル",
    "四国めたん:ノーマル",
    "春日部つむぎ:ノーマル",
    "玄野武宏:ノーマル",
    "青山龍星:ノーマル",
    "冥鳴ひまり:ノーマル",
]


class VoiceVoxClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or BASE_URL
        self._speakers = None

    def wait_ready(self, timeout=180):
        response = requests.get(f"{self.base_url}/version", timeout=timeout)
        response.raise_for_status()
        return response.text

    def speakers(self):
        if self._speakers is None:
            response = requests.get(f"{self.base_url}/speakers", timeout=30)
            response.raise_for_status()
            self._speakers = response.json()
        return self._speakers

    def resolve(self, name: str, style: str = "ノーマル") -> tuple[int, str]:
        for speaker in self.speakers():
            if speaker.get("name") != name:
                continue
            styles = speaker.get("styles") or []
            selected = next((x for x in styles if x.get("name") == style), None)
            selected = selected or next((x for x in styles if x.get("name") == "ノーマル"), None)
            selected = selected or (styles[0] if styles else None)
            if selected:
                return int(selected["id"]), f"{name}:{selected.get('name', style)}"
        raise RuntimeError(f"VOICEVOX voice not available: {name}:{style}")

    def choose_voice(self, project_id: str, explicit: dict | None = None) -> tuple[int, str]:
        explicit = explicit or {}
        if explicit.get("speaker_name"):
            return self.resolve(str(explicit["speaker_name"]), str(explicit.get("style_name") or "ノーマル"))

        raw = os.getenv("VOICE_ROTATION", "").strip()
        candidates = [x.strip() for x in raw.split(",") if x.strip()] if raw else list(DEFAULT_ROTATION)
        available = []
        for item in candidates:
            name, _, style = item.partition(":")
            try:
                available.append(self.resolve(name, style or "ノーマル"))
            except RuntimeError:
                continue
        if not available:
            speaker = self.speakers()[0]
            style = (speaker.get("styles") or [])[0]
            return int(style["id"]), f"{speaker['name']}:{style['name']}"
        digest = hashlib.sha256(project_id.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % len(available)
        return available[index]

    def audio_query(self, text: str, speaker_id: int, speed: float) -> dict:
        response = requests.post(
            f"{self.base_url}/audio_query",
            params={"text": text, "speaker": speaker_id},
            timeout=60,
        )
        response.raise_for_status()
        query = response.json()
        query["speedScale"] = float(speed)
        query["outputSamplingRate"] = 48000
        return query

    @staticmethod
    def estimate_query_seconds(query: dict) -> float:
        total = float(query.get("prePhonemeLength") or 0) + float(query.get("postPhonemeLength") or 0)
        for phrase in query.get("accentPhrases") or []:
            moras = list(phrase.get("moras") or [])
            pause = phrase.get("pauseMora")
            if pause:
                moras.append(pause)
            for mora in moras:
                total += float(mora.get("consonantLength") or 0)
                total += float(mora.get("vowelLength") or 0)
        speed = max(0.01, float(query.get("speedScale") or 1.0))
        return max(0.05, total / speed)

    def estimate_seconds(self, text: str, speaker_id: int, speed: float) -> float:
        return self.estimate_query_seconds(self.audio_query(text, speaker_id, speed))

    def synthesize(self, text: str, output_path: Path, speaker_id: int, speed: float) -> Path:
        query = self.audio_query(text, speaker_id, speed)
        response = requests.post(
            f"{self.base_url}/synthesis",
            params={"speaker": speaker_id},
            json=query,
            timeout=240,
        )
        response.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return output_path
