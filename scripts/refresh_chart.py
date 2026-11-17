"""Export Artificial Analysis' public chart using its own image download button."""

import argparse
import os
import re
import struct
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://artificialanalysis.ai/#intelligence-index-vs-cost-per-task-chart"
CHART = "#intelligence-index-vs-cost-per-task-chart"
STAMP = re.compile(r"<!-- chart-updated -->.*?<!-- /chart-updated -->", re.DOTALL)
READY = """(() => {
  const chart = document.querySelector('#intelligence-index-vs-cost-per-task-chart');
  return document.fonts.status === 'loaded' && chart &&
    chart.textContent.includes('Intelligence Index vs. Cost per Task') &&
    chart.textContent.includes('Cost per Task (USD, Log Scale)') &&
    chart.textContent.includes('Artificial Analysis') &&
    chart.textContent.includes('Pareto line') &&
    chart.querySelectorAll('circle').length >= 10 &&
    Array.from(chart.querySelectorAll('path[stroke-dasharray]')).some(
      path => path.getTotalLength() > 100);
})()"""


def validate_png(data: bytes) -> None:
    """Reject failed downloads, truncated images, and small placeholder exports."""
    if (
        len(data) < 30_000
        or data[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        or data[-12:] != b"\x00\x00\x00\x00IEND\xaeB`\x82"
    ):
        raise ValueError("Chart export is not a complete PNG")
    width, height = struct.unpack(">II", data[16:24])
    if not (1600 <= width <= 6000 and 800 <= height <= 4000):
        raise ValueError(f"Unexpected chart export dimensions: {width}x{height}")


def timestamp_readme(readme: str, captured_at: datetime) -> str:
    if len(STAMP.findall(readme)) != 1:
        raise ValueError("README must contain exactly one chart timestamp marker")
    date = captured_at.astimezone(UTC).strftime("%Y-%m-%d")
    return STAMP.sub(f"<!-- chart-updated -->Captured: {date} UTC.<!-- /chart-updated -->", readme)


def publish(downloaded: Path, root: Path = ROOT) -> None:
    data = downloaded.read_bytes()
    validate_png(data)
    readme_path = root / "README.md"
    updated_readme = timestamp_readme(readme_path.read_text(), datetime.now(UTC))
    image_path = root / "assets" / "intelligence-vs-cost.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(data)
    readme_path.write_text(updated_readme)
    print(f"Updated {image_path} from {SOURCE}")


def refresh(root: Path = ROOT) -> None:
    timestamp_readme((root / "README.md").read_text(), datetime.now(UTC))
    session = f"aa-profile-{uuid.uuid4().hex[:12]}"

    def browser(*args: str) -> None:
        subprocess.run(
            ["agent-browser", "--session", session, *args],
            check=True,
            timeout=120,
            env={**os.environ, "AGENT_BROWSER_DEFAULT_TIMEOUT": "90000"},
        )

    with tempfile.TemporaryDirectory(prefix="aa-chart-") as temporary:
        downloaded = Path(temporary) / "chart.png"
        try:
            browser("set", "viewport", "1440", "1000")
            browser("set", "media", "light", "reduced-motion")
            browser("open", SOURCE)
            browser("wait", "--fn", READY)
            browser("scrollintoview", CHART)
            browser(
                "download",
                f'{CHART} button[aria-label="Download chart as image"]',
                str(downloaded),
            )
            validate_png(downloaded.read_bytes())
        finally:
            browser("close")
        publish(downloaded, root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", type=Path, help="Publish an already captured PNG; no browser")
    args = parser.parse_args()
    if args.publish:
        publish(args.publish)
    else:
        refresh()
