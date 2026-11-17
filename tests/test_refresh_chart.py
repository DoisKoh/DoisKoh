import struct
import tempfile
import unittest
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.refresh_chart import publish, refresh, timestamp_readme, validate_png


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

    def test_accepts_native_export(self) -> None:
        validate_png(
            (Path(__file__).resolve().parents[1] / "assets/intelligence-vs-cost.png").read_bytes()
        )

    def test_timestamp_uses_utc_and_preserves_surrounding_text(self) -> None:
        readme = "before<!-- chart-updated -->old<!-- /chart-updated -->after"
        captured_at = datetime(2026, 11, 18, 1, tzinfo=timezone(timedelta(hours=8)))
        self.assertEqual(
            timestamp_readme(readme, captured_at),
            "before<!-- chart-updated -->Captured: 2026-11-17 UTC.<!-- /chart-updated -->after",
        )

    def test_rejects_missing_or_duplicate_timestamp(self) -> None:
        marker = "<!-- chart-updated -->old<!-- /chart-updated -->"
        for readme in ("no marker", marker * 2):
            with self.subTest(readme=readme), self.assertRaises(ValueError):
                timestamp_readme(readme, datetime.now(UTC))

    def test_browser_failure_preserves_chart_and_closes_session(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            readme = "<!-- chart-updated -->old<!-- /chart-updated -->"
            (root / "README.md").write_text(readme)
            (root / "assets").mkdir()
            image = root / "assets/intelligence-vs-cost.png"
            image.write_bytes(b"previous good chart")
            with patch("scripts.refresh_chart.subprocess.run") as run:
                run.side_effect = [None, None, RuntimeError("site unavailable"), None]
                with self.assertRaisesRegex(RuntimeError, "site unavailable"):
                    refresh(root)
                commands = [call.args[0] for call in run.call_args_list]
                self.assertEqual(commands[-1][-1], "close")
                self.assertEqual(len({command[2] for command in commands}), 1)
            self.assertEqual(image.read_bytes(), b"previous good chart")
            self.assertEqual((root / "README.md").read_text(), readme)

    def test_invalid_publish_preserves_readme(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text("unchanged")
            (root / "invalid.png").write_bytes(b"not an image")
            with self.assertRaises(ValueError):
                publish(root / "invalid.png", root)
            self.assertEqual((root / "README.md").read_text(), "unchanged")
            self.assertFalse((root / "assets").exists())


if __name__ == "__main__":
    unittest.main()
