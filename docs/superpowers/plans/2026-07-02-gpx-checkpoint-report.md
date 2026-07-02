# GPX Checkpoint Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dependency-free Python CLI that reports the first local time each GPX rider reaches every configured checkpoint.

**Architecture:** One importable Python module owns configuration validation, Haversine distance calculation, streaming GPX parsing, CSV generation, and the CLI entry point. Built-in `unittest` integration tests exercise the public functions with temporary GPX/config files; a checked-in JSON file provides the editable runtime configuration.

**Tech Stack:** Python 3.9+, standard-library `csv`, `datetime`, `json`, `pathlib`, `unittest`, `xml.etree.ElementTree`, and `zoneinfo`.

## Global Constraints

- Use only Python's standard library.
- Read `checkpoints.json` and `*.gpx` from the current working directory.
- Write `report.csv` to the current working directory.
- Record only the first track point within or exactly on `radius_m`.
- Convert GPX timestamps to the explicitly configured IANA timezone.
- Format reported values as `HH:MM:SS`.
- Preserve configured checkpoint order and sort rider rows by filename.
- Leave unreached checkpoint cells empty.

---

### Task 1: GPX checkpoint detection

**Files:**
- Create: `gpx_checkpoint_report.py`
- Create: `test_gpx_checkpoint_report.py`

**Interfaces:**
- Produces: `Checkpoint(name: str, latitude: float, longitude: float)`
- Produces: `haversine_m(latitude_1: float, longitude_1: float, latitude_2: float, longitude_2: float) -> float`
- Produces: `find_checkpoint_times(gpx_path: Path, checkpoints: tuple[Checkpoint, ...], radius_m: float, timezone: ZoneInfo) -> dict[str, str]`

- [ ] **Step 1: Write failing unit and GPX parsing tests**

Create `test_gpx_checkpoint_report.py` with:

```python
import tempfile
import unittest
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from gpx_checkpoint_report import Checkpoint, find_checkpoint_times, haversine_m


def write_gpx(
    path: Path, points: list[tuple[float, float, Optional[str]]]
) -> None:
    track_points = []
    for latitude, longitude, timestamp in points:
        time_element = f"<time>{timestamp}</time>" if timestamp else ""
        track_points.append(
            f'<trkpt lat="{latitude}" lon="{longitude}">{time_element}</trkpt>'
        )
    path.write_text(
        '<?xml version="1.0"?>'
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">'
        f"<trk><trkseg>{''.join(track_points)}</trkseg></trk>"
        "</gpx>",
        encoding="utf-8",
    )


class GpxCheckpointTests(unittest.TestCase):
    def test_haversine_calculates_short_distance_in_metres(self) -> None:
        distance = haversine_m(0.0, 0.0, 0.0, 0.000179864)

        self.assertAlmostEqual(distance, 20.0, delta=0.05)

    def test_records_first_visit_and_converts_it_to_configured_timezone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            gpx_path = Path(directory) / "rider.gpx"
            write_gpx(
                gpx_path,
                [
                    (47.001, 28.001, "2026-07-01T00:59:00Z"),
                    (47.0, 28.0, "2026-07-01T01:00:00Z"),
                    (47.001, 28.001, "2026-07-01T01:01:00Z"),
                    (47.0, 28.0, "2026-07-01T02:00:00Z"),
                ],
            )

            result = find_checkpoint_times(
                gpx_path,
                (Checkpoint("start", 47.0, 28.0),),
                20.0,
                ZoneInfo("Europe/Chisinau"),
            )

        self.assertEqual(result, {"start": "04:00:00"})

    def test_leaves_unreached_checkpoint_out_of_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            gpx_path = Path(directory) / "rider.gpx"
            write_gpx(gpx_path, [(47.0, 28.0, "2026-07-01T01:00:00Z")])

            result = find_checkpoint_times(
                gpx_path,
                (Checkpoint("elsewhere", 48.0, 29.0),),
                20.0,
                ZoneInfo("UTC"),
            )

        self.assertEqual(result, {})

    def test_rejects_reached_track_point_without_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            gpx_path = Path(directory) / "rider.gpx"
            write_gpx(gpx_path, [(47.0, 28.0, None)])

            with self.assertRaisesRegex(ValueError, "missing a timestamp"):
                find_checkpoint_times(
                    gpx_path,
                    (Checkpoint("start", 47.0, 28.0),),
                    20.0,
                    ZoneInfo("UTC"),
                )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify the import fails**

Run:

```bash
python3 -m unittest test_gpx_checkpoint_report.py
```

Expected: error with `ModuleNotFoundError: No module named 'gpx_checkpoint_report'`.

- [ ] **Step 3: Implement distance and streaming GPX parsing**

Create `gpx_checkpoint_report.py` with:

```python
from __future__ import annotations

import math
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class Checkpoint:
    name: str
    latitude: float
    longitude: float


def haversine_m(
    latitude_1: float,
    longitude_1: float,
    latitude_2: float,
    longitude_2: float,
) -> float:
    latitude_1_rad = math.radians(latitude_1)
    latitude_2_rad = math.radians(latitude_2)
    latitude_delta = math.radians(latitude_2 - latitude_1)
    longitude_delta = math.radians(longitude_2 - longitude_1)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(latitude_1_rad)
        * math.cos(latitude_2_rad)
        * math.sin(longitude_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(haversine))


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_time(value: str, gpx_path: Path) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{gpx_path}: invalid timestamp {value!r}") from error
    if timestamp.tzinfo is None:
        raise ValueError(f"{gpx_path}: timestamp {value!r} has no timezone")
    return timestamp


def find_checkpoint_times(
    gpx_path: Path,
    checkpoints: tuple[Checkpoint, ...],
    radius_m: float,
    timezone: ZoneInfo,
) -> dict[str, str]:
    found: dict[str, str] = {}
    pending = {checkpoint.name: checkpoint for checkpoint in checkpoints}

    try:
        elements = ElementTree.iterparse(gpx_path, events=("end",))
        for _, element in elements:
            if _local_name(element.tag) != "trkpt":
                continue
            try:
                latitude = float(element.attrib["lat"])
                longitude = float(element.attrib["lon"])
            except (KeyError, ValueError) as error:
                raise ValueError(
                    f"{gpx_path}: track point has invalid coordinates"
                ) from error
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError(f"{gpx_path}: track point coordinates are out of range")

            reached = [
                checkpoint
                for checkpoint in pending.values()
                if haversine_m(
                    latitude,
                    longitude,
                    checkpoint.latitude,
                    checkpoint.longitude,
                )
                <= radius_m
            ]
            if reached:
                time_element = next(
                    (
                        child
                        for child in element
                        if _local_name(child.tag) == "time" and child.text
                    ),
                    None,
                )
                if time_element is None:
                    raise ValueError(
                        f"{gpx_path}: reached track point is missing a timestamp"
                    )
                local_time = _parse_time(time_element.text, gpx_path).astimezone(
                    timezone
                )
                for checkpoint in reached:
                    found[checkpoint.name] = local_time.strftime("%H:%M:%S")
                    del pending[checkpoint.name]
            element.clear()
    except ElementTree.ParseError as error:
        raise ValueError(f"{gpx_path}: malformed GPX XML") from error

    return found
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
python3 -m unittest test_gpx_checkpoint_report.py
```

Expected: `Ran 4 tests` and `OK`.

- [ ] **Step 5: Commit checkpoint detection**

```bash
git add gpx_checkpoint_report.py test_gpx_checkpoint_report.py
git commit -m "FB_DEVOPS-0_fisakov add GPX checkpoint detection"
```

### Task 2: Configuration and CSV report

**Files:**
- Modify: `gpx_checkpoint_report.py`
- Modify: `test_gpx_checkpoint_report.py`
- Create: `checkpoints.json`

**Interfaces:**
- Consumes: `Checkpoint` and `find_checkpoint_times(...)` from Task 1.
- Produces: `Config(timezone: ZoneInfo, radius_m: float, checkpoints: tuple[Checkpoint, ...])`
- Produces: `load_config(path: Path) -> Config`
- Produces: `generate_report(directory: Path, config_name: str = "checkpoints.json", output_name: str = "report.csv") -> Path`
- Produces: `main() -> int`

- [ ] **Step 1: Add failing configuration and report tests**

Add these imports to `test_gpx_checkpoint_report.py`:

```python
import csv
import json

from gpx_checkpoint_report import (
    Checkpoint,
    find_checkpoint_times,
    generate_report,
    haversine_m,
    load_config,
)
```

Add these tests to `GpxCheckpointTests`:

```python
    def test_generates_dynamic_columns_sorted_by_gpx_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_directory = Path(directory)
            (runtime_directory / "checkpoints.json").write_text(
                json.dumps(
                    {
                        "timezone": "Europe/Chisinau",
                        "radius_m": 20,
                        "checkpoints": [
                            {
                                "name": "finish",
                                "latitude": 47.1,
                                "longitude": 28.1,
                            },
                            {
                                "name": "start",
                                "latitude": 47.0,
                                "longitude": 28.0,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            write_gpx(
                runtime_directory / "zoe.gpx",
                [(47.0, 28.0, "2026-07-01T01:00:00Z")],
            )
            write_gpx(
                runtime_directory / "amy.gpx",
                [(47.1, 28.1, "2026-07-01T02:00:00Z")],
            )

            report_path = generate_report(runtime_directory)

            with report_path.open(newline="", encoding="utf-8") as report:
                rows = list(csv.reader(report))

        self.assertEqual(
            rows,
            [
                ["user_name", "finish", "start"],
                ["amy", "05:00:00", ""],
                ["zoe", "", "04:00:00"],
            ],
        )

    def test_rejects_duplicate_checkpoint_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "checkpoints.json"
            config_path.write_text(
                json.dumps(
                    {
                        "timezone": "UTC",
                        "radius_m": 20,
                        "checkpoints": [
                            {"name": "same", "latitude": 47.0, "longitude": 28.0},
                            {"name": "same", "latitude": 48.0, "longitude": 29.0},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unique"):
                load_config(config_path)
```

- [ ] **Step 2: Run the new tests and verify the import fails**

Run:

```bash
python3 -m unittest test_gpx_checkpoint_report.py
```

Expected: error with `ImportError: cannot import name 'generate_report'`.

- [ ] **Step 3: Implement validated config, report generation, and CLI**

Add these imports near the top of `gpx_checkpoint_report.py`:

```python
import csv
import json
import sys
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
```

Add after `Checkpoint`:

```python
@dataclass(frozen=True)
class Config:
    timezone: ZoneInfo
    radius_m: float
    checkpoints: tuple[Checkpoint, ...]


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    return float(value)


def load_config(path: Path) -> Config:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: unable to read valid JSON configuration") from error
    if not isinstance(data, dict):
        raise ValueError(f"{path}: configuration must be a JSON object")

    timezone_name = data.get("timezone")
    if not isinstance(timezone_name, str) or not timezone_name:
        raise ValueError(f"{path}: timezone must be a non-empty string")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"{path}: unknown timezone {timezone_name!r}") from error

    radius_m = _number(data.get("radius_m"), "radius_m")
    if radius_m <= 0:
        raise ValueError(f"{path}: radius_m must be greater than zero")

    raw_checkpoints = data.get("checkpoints")
    if not isinstance(raw_checkpoints, list) or not raw_checkpoints:
        raise ValueError(f"{path}: checkpoints must be a non-empty list")

    checkpoints: list[Checkpoint] = []
    names: set[str] = set()
    for index, raw_checkpoint in enumerate(raw_checkpoints):
        if not isinstance(raw_checkpoint, dict):
            raise ValueError(f"{path}: checkpoint {index} must be an object")
        name = raw_checkpoint.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{path}: checkpoint {index} name must be non-empty")
        if name in names:
            raise ValueError(f"{path}: checkpoint names must be unique")
        latitude = _number(
            raw_checkpoint.get("latitude"), f"checkpoint {name} latitude"
        )
        longitude = _number(
            raw_checkpoint.get("longitude"), f"checkpoint {name} longitude"
        )
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError(f"{path}: checkpoint {name} coordinates are out of range")
        checkpoints.append(Checkpoint(name, latitude, longitude))
        names.add(name)

    return Config(timezone, radius_m, tuple(checkpoints))
```

Add after `find_checkpoint_times`:

```python
def generate_report(
    directory: Path,
    config_name: str = "checkpoints.json",
    output_name: str = "report.csv",
) -> Path:
    config = load_config(directory / config_name)
    output_path = directory / output_name
    gpx_paths = sorted(directory.glob("*.gpx"), key=lambda path: path.name)

    try:
        with output_path.open("w", newline="", encoding="utf-8") as report:
            writer = csv.writer(report)
            writer.writerow(
                ["user_name", *(checkpoint.name for checkpoint in config.checkpoints)]
            )
            for gpx_path in gpx_paths:
                times = find_checkpoint_times(
                    gpx_path,
                    config.checkpoints,
                    config.radius_m,
                    config.timezone,
                )
                writer.writerow(
                    [
                        gpx_path.stem,
                        *(times.get(checkpoint.name, "") for checkpoint in config.checkpoints),
                    ]
                )
    except OSError as error:
        raise ValueError(f"{output_path}: unable to write report") from error

    return output_path


def main() -> int:
    try:
        generate_report(Path.cwd())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `checkpoints.json`:

```json
{
  "timezone": "Europe/Chisinau",
  "radius_m": 20,
  "checkpoints": [
    {
      "name": "checkpoint_1",
      "latitude": 47.081821,
      "longitude": 28.769529
    }
  ]
}
```

- [ ] **Step 4: Run all tests and verify they pass**

Run:

```bash
python3 -m unittest -v
```

Expected: `Ran 6 tests` and `OK`.

- [ ] **Step 5: Commit report generation**

```bash
git add gpx_checkpoint_report.py test_gpx_checkpoint_report.py checkpoints.json
git commit -m "FB_DEVOPS-0_fisakov generate checkpoint CSV reports"
```

### Task 3: Usage documentation and sample-file verification

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: the zero-argument CLI and JSON schema from Task 2.
- Produces: user-facing setup, configuration, execution, and output instructions.

- [ ] **Step 1: Write usage documentation**

Create `README.md` with:

```markdown
# GPX checkpoint report

Generate a CSV showing the first local time each rider came within a configured
distance of each checkpoint.

## Requirements

- Python 3.9 or newer
- GPX files containing timestamped track points, such as Strava exports

No third-party packages are required.

## Configure

Edit `checkpoints.json`:

```json
{
  "timezone": "Europe/Chisinau",
  "radius_m": 20,
  "checkpoints": [
    {
      "name": "checkpoint_1",
      "latitude": 47.081821,
      "longitude": 28.769529
    }
  ]
}
```

Checkpoint names become CSV columns in the same order. Use an
[IANA timezone name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

## Run

Put `checkpoints.json`, the script, and one or more `*.gpx` files in the same
directory, then run:

```bash
python3 gpx_checkpoint_report.py
```

The script creates `report.csv`:

```csv
user_name,checkpoint_1
Yurii_fisakov,04:14:09
```

The user name is the GPX filename without `.gpx`. An empty checkpoint cell
means the track never came within `radius_m` of that checkpoint. If a track
enters the checkpoint radius more than once, only its first visit is reported.
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
python3 -m unittest -v
```

Expected: `Ran 6 tests` and `OK`.

- [ ] **Step 3: Verify the CLI with the uploaded Strava GPX**

Copy the untracked uploaded file to a temporary directory with a `.gpx`
extension, copy the script/config there, run the CLI, and print the bounded
report:

```bash
runtime_directory="$(mktemp -d)"
cp Yurii_fisakov "$runtime_directory/Yurii_fisakov.gpx"
cp gpx_checkpoint_report.py checkpoints.json "$runtime_directory/"
(cd "$runtime_directory" && python3 gpx_checkpoint_report.py)
head -c 1000 "$runtime_directory/report.csv"
rm -rf "$runtime_directory"
```

Expected:

```csv
user_name,checkpoint_1
Yurii_fisakov,04:14:09
```

- [ ] **Step 4: Check the final diff**

Run:

```bash
git diff --check HEAD
git status --short
```

Expected: no whitespace errors; only `README.md` is newly uncommitted and the
uploaded `Yurii_fisakov` remains untracked.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md
git commit -m "FB_DEVOPS-0_fisakov document GPX report usage"
```
