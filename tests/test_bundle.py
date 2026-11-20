import hashlib
import json
import struct
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.refresh_chart import CHARTS, publish, refresh, timestamp_readme, validate_png

ROOT = Path(__file__).resolve().parents[1]
README = "before<!-- chart-updated -->old<!-- /chart-updated -->after"


def make_bundle(directory: Path, captured_at: str = "2026-11-16T20:00:00+00:00") -> None:
    directory.mkdir()
    for filename in CHARTS:
        (directory / filename).write_bytes((ROOT / "assets" / filename).read_bytes())
    metadata = {
        "captured_at": captured_at,
        "index_version": "v5.0.1",
        "sha256": {
            filename: hashlib.sha256((directory / filename).read_bytes()).hexdigest()
            for filename in CHARTS
        },
    }
    (directory / "captured.json").write_text(json.dumps(metadata))


class RefreshChartTests(unittest.TestCase):
    def test_rejects_invalid_exports(self) -> None:
        for data in (b"", b"<html>Cloudflare error</html>", b"\x89PNG" + bytes(40_000)):
            with self.subTest(data=data[:30]), self.assertRaises(ValueError):
                validate_png(data)

    def test_rejects_small_export(self) -> None:
        data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            + struct.pack(">II", 400, 200)
            + bytes(40_000)
            + b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        with self.assertRaisesRegex(ValueError, "dimensions"):
            validate_png(data)

    def test_accepts_both_native_exports(self) -> None:
        for filename in CHARTS:
            with self.subTest(filename=filename):
                validate_png((ROOT / "assets" / filename).read_bytes())

    def test_timestamp_uses_utc_and_preserves_surrounding_text(self) -> None:
        captured_at = datetime(2026, 11, 18, 1, tzinfo=timezone(timedelta(hours=8)))
        self.assertEqual(
            timestamp_readme(README, captured_at, "v5.0.1"),
            "before<!-- chart-updated -->_Captured: 2026-11-17 UTC_<!-- /chart-updated -->after",
        )

    def test_rejects_missing_or_duplicate_timestamp(self) -> None:
        marker = "<!-- chart-updated -->old<!-- /chart-updated -->"
        for readme in ("no marker", marker * 2):
            with self.subTest(readme=readme), self.assertRaises(ValueError):
                timestamp_readme(readme, datetime.now(UTC), "v5.0.1")

    def test_rejects_invalid_index_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "version"):
            timestamp_readme(README, datetime.now(UTC), "unknown")

    def test_publish_preserves_actual_capture_date_on_later_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text(README)
            make_bundle(root / "capture")
            publish(root / "capture", root)
            self.assertIn("_Captured: 2026-11-16 UTC_", (root / "README.md").read_text())
            for filename in (*CHARTS, "captured.json"):
                self.assertEqual(
                    (root / "assets" / filename).read_bytes(),
                    (root / "capture" / filename).read_bytes(),
                )

    def test_bad_second_chart_never_updates_first_chart_or_date(self) -> None:
        for failure in ("missing", "corrupt", "checksum"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "README.md").write_text(README)
                (root / "assets").mkdir()
                image = root / "assets/intelligence-vs-cost.png"
                image.write_bytes(b"previous good chart")
                make_bundle(root / "capture")
                capability = root / "capture/capability-index-comparison.png"
                if failure == "missing":
                    capability.unlink()
                elif failure == "corrupt":
                    capability.write_bytes(b"broken export")
                else:
                    data = bytearray(capability.read_bytes())
                    data[100] ^= 1
                    capability.write_bytes(data)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    publish(root / "capture", root)
                self.assertEqual(image.read_bytes(), b"previous good chart")
                self.assertEqual((root / "README.md").read_text(), README)

    def test_old_publish_retry_cannot_roll_back_newer_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text(README)
            make_bundle(root / "newer", "2026-11-17T20:00:00+00:00")
            make_bundle(root / "older", "2026-11-16T20:00:00+00:00")
            publish(root / "newer", root)
            published = (root / "assets/captured.json").read_bytes()
            readme = (root / "README.md").read_text()
            publish(root / "older", root)
            self.assertEqual((root / "assets/captured.json").read_bytes(), published)
            self.assertEqual((root / "README.md").read_text(), readme)

    def test_browser_failure_preserves_charts_and_closes_session(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text(README)
            (root / "assets").mkdir()
            for filename in CHARTS:
                (root / "assets" / filename).write_bytes(b"previous good chart")
            success: subprocess.CompletedProcess[str] = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            with patch("scripts.refresh_chart.subprocess.run") as run:
                run.side_effect = [success, success, RuntimeError("site unavailable"), success]
                with self.assertRaisesRegex(RuntimeError, "site unavailable"):
                    refresh(root)
                commands = [call.args[0] for call in run.call_args_list]
                self.assertEqual(commands[-1][-1], "close")
                self.assertEqual(len({command[2] for command in commands}), 1)
            for filename in CHARTS:
                self.assertEqual((root / "assets" / filename).read_bytes(), b"previous good chart")
            self.assertEqual((root / "README.md").read_text(), README)


if __name__ == "__main__":
    unittest.main()
