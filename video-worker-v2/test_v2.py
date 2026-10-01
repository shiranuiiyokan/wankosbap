import tempfile
import unittest
from pathlib import Path

from manifest import normalize_manifest, narration_groups
from pronunciation import normalize_tts_text, apply_readings, unresolved_risks


class PronunciationTests(unittest.TestCase):
    def test_japanese_spaces_removed(self):
        self.assertEqual(normalize_tts_text("柴犬 は 日本犬 です。"), "柴犬は日本犬です。")

    def test_reading_map(self):
        self.assertEqual(apply_readings("前回のJKC", {"前回": "ぜんかい", "JKC": "ジェーケーシー"}), "ぜんかいのジェーケーシー")

    def test_unknown_latin_flagged(self):
        self.assertIn("XYZ", unresolved_risks("XYZを確認", {"JKC"}))


class ManifestTests(unittest.TestCase):
    def test_duration_seconds_and_root_image_compatibility(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "scene01.png").write_bytes(b"x")
            raw = {
                "project_id": "T1",
                "video": {"width": 1080, "height": 1920},
                "scenes": [{
                    "image": "images/scene01.png",
                    "narration": "テストです。",
                    "duration_seconds": 8.2,
                    "chapter": "導入"
                }]
            }
            job = normalize_manifest(raw, "dog", root)
            self.assertEqual(job["scenes"][0]["duration_hint"], 8.2)
            self.assertEqual(job["scenes"][0]["image"], "scene01.png")

    def test_short_is_single_narration_group(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("a.png", "b.png"):
                (root / name).write_bytes(b"x")
            raw = {"scenes": [
                {"image": "a.png", "narration": "A。", "chapter": "one"},
                {"image": "b.png", "narration": "B。", "chapter": "two"},
            ]}
            job = normalize_manifest(raw, "dog", root)
            self.assertEqual(len(narration_groups(job)), 1)


if __name__ == "__main__":
    unittest.main()
