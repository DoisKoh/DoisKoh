"""Export Artificial Analysis' public chart using its own image download button."""

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://artificialanalysis.ai/#intelligence"
STAMP = re.compile(r"<!-- chart-updated -->.*?<!-- /chart-updated -->", re.DOTALL)
COST_READY = """(() => {
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
CAPABILITY_READY = """(() => {
  const chart = document.querySelector('#capability-index-comparison-chart');
  return document.fonts.status === 'loaded' && chart &&
    ['Capability Index Comparison', 'Finance & Accounting', 'Strategy & Ops',
     'Legal', 'Healthcare & Medical', 'Engineering', 'Economics'].every(
       label => chart.textContent.includes(label)) &&
    chart.querySelectorAll('circle').length >= 60 &&
    chart.querySelectorAll('path').length >= 10;
})()"""
CHARTS = {
    "intelligence-vs-cost.png": ("intelligence-index-vs-cost-per-task-chart", COST_READY),
    "capability-index-comparison.png": ("capability-index-comparison-chart", CAPABILITY_READY),
}
VERSION = (
    r"document.body.innerText.match("
    r"/Artificial Analysis Intelligence Index (v\d+(?:\.\d+){1,2})\b/)?.[1]"
)


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


def timestamp_readme(readme: str, captured_at: datetime, version: str) -> str:
    if len(STAMP.findall(readme)) != 1:
        raise ValueError("README must contain exactly one chart timestamp marker")
    date = captured_at.astimezone(UTC).strftime("%Y-%m-%d")
    if not re.fullmatch(r"v\d+(?:\.\d+){1,2}", version):
        raise ValueError("Missing or invalid Intelligence Index version")
    return STAMP.sub(
        f"<!-- chart-updated -->\n\n_Captured: {date} UTC_\n\n<!-- /chart-updated -->", readme
    )


def publish(capture_dir: Path, root: Path = ROOT) -> None:
    metadata_bytes = (capture_dir / "captured.json").read_bytes()
    metadata = json.loads(metadata_bytes)
    captured_at = datetime.fromisoformat(metadata["captured_at"])
    if captured_at.utcoffset() != UTC.utcoffset(captured_at):
        raise ValueError("Capture timestamp must include UTC timezone")
    if set(metadata["sha256"]) != set(CHARTS):
        raise ValueError("Capture must contain both expected charts")
    images = {}
    for filename in CHARTS:
        data = (capture_dir / filename).read_bytes()
        validate_png(data)
        if hashlib.sha256(data).hexdigest() != metadata["sha256"][filename]:
            raise ValueError(f"Capture checksum mismatch: {filename}")
        images[filename] = data
    current_metadata = root / "assets/captured.json"
    if current_metadata.exists():
        current_time = datetime.fromisoformat(
            json.loads(current_metadata.read_bytes())["captured_at"]
        )
        if captured_at < current_time:
            print("Skipped an older capture; newer charts are already published")
            return
    readme_path = root / "README.md"
    updated_readme = timestamp_readme(
        readme_path.read_text(), captured_at, metadata["index_version"]
    )
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for filename, data in images.items():
        (assets / filename).write_bytes(data)
    (assets / "captured.json").write_bytes(metadata_bytes)
    readme_path.write_text(updated_readme)
    print(f"Updated both charts from {SOURCE}; captured {captured_at.isoformat()}")


def refresh(root: Path = ROOT) -> None:
    timestamp_readme((root / "README.md").read_text(), datetime.now(UTC), "v0.0")
    session = f"aa-profile-{uuid.uuid4().hex[:12]}"

    def browser(*args: str, script: str | None = None) -> str:
        result = subprocess.run(
            ["agent-browser", "--session", session, *args],
            check=False,
            timeout=120,
            env={**os.environ, "AGENT_BROWSER_DEFAULT_TIMEOUT": "90000"},
            input=script,
            text=True,
            capture_output=True,
        )
        if args[0] != "eval":
            print(result.stdout.strip(), flush=True)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        result.check_returncode()
        return result.stdout

    with tempfile.TemporaryDirectory(prefix="aa-chart-") as temporary:
        capture_dir = Path(temporary)
        try:
            browser("set", "viewport", "1440", "1000")
            browser("set", "media", "light", "reduced-motion")
            browser("open", SOURCE)
            for filename, (chart_id, ready) in CHARTS.items():
                browser("scrollintoview", f"#{chart_id}")
                deadline = time.monotonic() + 90
                while not json.loads(browser("eval", "--stdin", script=ready)):
                    if time.monotonic() >= deadline:
                        diagnostics = (
                            "(() => {const chart = document.getElementById("
                            + json.dumps(chart_id)
                            + "); return {title: document.title, fonts: document.fonts.status, "
                            "circles: chart?.querySelectorAll('circle').length, "
                            "dottedPaths: chart?.querySelectorAll("
                            "'path[stroke-dasharray]').length, "
                            "taskCostAxis: chart?.textContent.includes("
                            "'Cost per Task (USD, Log Scale)')}})()"
                        )
                        print(browser("eval", "--stdin", script=diagnostics), flush=True)
                        raise TimeoutError(f"Chart not ready: {chart_id}")
                    time.sleep(0.5)
                browser(
                    "download",
                    f'#{chart_id} button[aria-label="Download chart as image"]',
                    str(capture_dir / filename),
                )
                validate_png((capture_dir / filename).read_bytes())
            version = json.loads(browser("eval", "--stdin", script=VERSION))
            timestamp_readme((root / "README.md").read_text(), datetime.now(UTC), version)
            metadata = {
                "captured_at": datetime.now(UTC).isoformat(),
                "index_version": version,
                "sha256": {
                    filename: hashlib.sha256((capture_dir / filename).read_bytes()).hexdigest()
                    for filename in CHARTS
                },
            }
            (capture_dir / "captured.json").write_text(json.dumps(metadata, indent=2) + "\n")
        finally:
            browser("close")
        publish(capture_dir, root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publish", type=Path, help="Publish an already captured bundle; no browser"
    )
    args = parser.parse_args()
    if args.publish:
        publish(args.publish)
    else:
        refresh()
