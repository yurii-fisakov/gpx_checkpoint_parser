# Local GPX Checkpoint Web Application Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local webpage for editable checkpoint configuration, multiple GPX uploads, an on-page report, and CSV download while preserving the CLI.

**Architecture:** Extract a small row-building API from the existing report generator, then call it from a stateless Flask JSON endpoint. A single server-rendered page uses plain JavaScript for dynamic checkpoint rows, submission, report rendering, and CSV download.

**Tech Stack:** Python 3.9+, Flask 3.1.x, `unittest`, HTML, CSS, browser JavaScript

## Global Constraints

- The server runs locally and binds to `127.0.0.1` with debug mode disabled.
- Initial radius and checkpoint rows come from `checkpoints.json`.
- The browser supplies its IANA timezone.
- The number of checkpoint rows is unrestricted; each row can be deleted.
- At least one checkpoint and one `.gpx` upload are required for report generation.
- Uploaded files and generated reports are not persisted.
- The existing CLI behavior and CSV format remain unchanged.
- Flask is the only new runtime dependency.

---

### Task 1: Expose shared configuration and report-row APIs

**Files:**
- Modify: `gpx_checkpoint_report.py:33-88`
- Modify: `gpx_checkpoint_report.py:201-235`
- Test: `test_gpx_checkpoint_report.py`

**Interfaces:**
- Produces: `parse_config(data: Any, source: str = "configuration") -> Config`
- Produces: `build_report_rows(gpx_paths: list[Path], config: Config) -> list[list[str]]`
- Preserves: `load_config(path: Path) -> Config`
- Preserves: `generate_report(directory: Path, config_name: str = "checkpoints.json", output_name: str = "report.csv") -> Path`

- [ ] **Step 1: Write failing tests for in-memory configuration and report rows**

Add `parse_config` and `build_report_rows` to the imports in
`test_gpx_checkpoint_report.py`, then add:

```python
    def test_parses_in_memory_configuration(self) -> None:
        config = parse_config(
            {
                "timezone": "Europe/Chisinau",
                "radius_m": 25,
                "checkpoints": [
                    {"name": "start", "latitude": 47.0, "longitude": 28.0}
                ],
            }
        )

        self.assertEqual(config.timezone, ZoneInfo("Europe/Chisinau"))
        self.assertEqual(config.radius_m, 25.0)
        self.assertEqual(
            config.checkpoints,
            (Checkpoint("start", 47.0, 28.0),),
        )

    def test_builds_rows_from_explicit_paths_and_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_directory = Path(directory)
            write_gpx(
                runtime_directory / "zoe.gpx",
                [(47.0, 28.0, "2026-07-01T01:00:00Z")],
            )
            write_gpx(
                runtime_directory / "amy.gpx",
                [(48.0, 29.0, "2026-07-01T02:00:00Z")],
            )
            config = Config(
                ZoneInfo("Europe/Chisinau"),
                20.0,
                (Checkpoint("start", 47.0, 28.0),),
            )

            rows = build_report_rows(
                [
                    runtime_directory / "zoe.gpx",
                    runtime_directory / "amy.gpx",
                ],
                config,
            )

        self.assertEqual(
            rows,
            [
                ["user_name", "start"],
                ["amy", ""],
                ["zoe", "04:00:00"],
            ],
        )
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
bash -o pipefail -c 'rtk python3 -m unittest \
  test_gpx_checkpoint_report.GpxCheckpointTests.test_parses_in_memory_configuration \
  test_gpx_checkpoint_report.GpxCheckpointTests.test_builds_rows_from_explicit_paths_and_configuration \
  2>&1 | tail -c 2000'
```

Expected: import failure because `parse_config` and `build_report_rows` do not
exist.

- [ ] **Step 3: Implement the minimal shared APIs**

In `gpx_checkpoint_report.py`, move the validation portion of `load_config`
into:

```python
def parse_config(data: Any, source: str = "configuration") -> Config:
    if not isinstance(data, dict):
        raise ValueError(f"{source}: configuration must be a JSON object")

    timezone_name = data.get("timezone")
    if not isinstance(timezone_name, str) or not timezone_name:
        raise ValueError(f"{source}: timezone must be a non-empty string")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"{source}: unknown timezone {timezone_name!r}") from error

    radius_m = _number(data.get("radius_m"), "radius_m")
    if radius_m <= 0:
        raise ValueError("radius_m must be greater than zero")

    raw_checkpoints = data.get("checkpoints")
    if not isinstance(raw_checkpoints, list) or not raw_checkpoints:
        raise ValueError(f"{source}: checkpoints must be a non-empty list")

    checkpoints: list[Checkpoint] = []
    names: set[str] = set()
    for index, raw_checkpoint in enumerate(raw_checkpoints):
        if not isinstance(raw_checkpoint, dict):
            raise ValueError(f"{source}: checkpoint {index} must be an object")
        name = raw_checkpoint.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{source}: checkpoint {index} name must be non-empty")
        if name in names:
            raise ValueError(f"{source}: checkpoint names must be unique")
        latitude = _number(
            raw_checkpoint.get("latitude"), f"checkpoint {name} latitude"
        )
        longitude = _number(
            raw_checkpoint.get("longitude"), f"checkpoint {name} longitude"
        )
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError(f"{source}: checkpoint {name} coordinates are out of range")
        checkpoints.append(Checkpoint(name, latitude, longitude))
        names.add(name)

    return Config(timezone, radius_m, tuple(checkpoints))
```

Keep file reading in `load_config` and delegate after successful JSON parsing:

```python
def load_config(path: Path) -> Config:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: unable to read valid JSON configuration") from error
    return parse_config(data, str(path))
```

Add the row API and make `generate_report` write its result:

```python
def build_report_rows(
    gpx_paths: list[Path],
    config: Config,
) -> list[list[str]]:
    rows = [
        ["user_name", *(checkpoint.name for checkpoint in config.checkpoints)]
    ]
    for gpx_path in sorted(gpx_paths, key=lambda path: path.name):
        times = find_checkpoint_times(
            gpx_path,
            config.checkpoints,
            config.radius_m,
            config.timezone,
        )
        rows.append(
            [
                gpx_path.stem,
                *(
                    times.get(checkpoint.name, "")
                    for checkpoint in config.checkpoints
                ),
            ]
        )
    return rows


def generate_report(
    directory: Path,
    config_name: str = "checkpoints.json",
    output_name: str = "report.csv",
) -> Path:
    config = load_config(directory / config_name)
    output_path = directory / output_name
    rows = build_report_rows(list(directory.glob("*.gpx")), config)

    try:
        with output_path.open("w", newline="", encoding="utf-8") as report:
            csv.writer(report).writerows(rows)
    except OSError as error:
        raise ValueError(f"{output_path}: unable to write report") from error

    return output_path
```

- [ ] **Step 4: Run the focused tests and existing parser suite**

Run:

```bash
bash -o pipefail -c 'rtk python3 -m unittest test_gpx_checkpoint_report \
  2>&1 | tail -c 3000'
```

Expected: all tests pass with no errors.

- [ ] **Step 5: Commit the shared API**

```bash
git add gpx_checkpoint_report.py test_gpx_checkpoint_report.py
git commit -m "FB_DEVOPS-0_fisakov expose shared report API"
```

### Task 2: Add the Flask report endpoint

**Files:**
- Create: `web_app.py`
- Create: `test_web_app.py`
- Create: `requirements.txt`

**Interfaces:**
- Consumes: `parse_config(data: Any, source: str) -> Config`
- Consumes: `build_report_rows(gpx_paths: list[Path], config: Config) -> list[list[str]]`
- Produces: `create_app(config_path: Optional[Path] = None) -> Flask`
- Produces: `GET /`
- Produces: `POST /api/report`

- [ ] **Step 1: Write failing endpoint tests**

Create `test_web_app.py`:

```python
import io
import json
import tempfile
import unittest
from pathlib import Path

from web_app import create_app


GPX = b"""<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <trk><trkseg>
    <trkpt lat="47.0" lon="28.0"><time>2026-07-01T01:00:00Z</time></trkpt>
  </trkseg></trk>
</gpx>
"""


class WebAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temporary_directory.name) / "checkpoints.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "timezone": "UTC",
                    "radius_m": 20,
                    "checkpoints": [
                        {"name": "default", "latitude": 47.0, "longitude": 28.0}
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.app = create_app(self.config_path)
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_home_page_contains_default_configuration(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"name": "default"', response.data)
        self.assertIn(b'"radius_m": 20.0', response.data)

    def test_generates_report_for_uploaded_files_and_browser_timezone(self) -> None:
        configuration = {
            "timezone": "Europe/Chisinau",
            "radius_m": 20,
            "checkpoints": [
                {"name": "start", "latitude": 47.0, "longitude": 28.0},
                {"name": "elsewhere", "latitude": 48.0, "longitude": 29.0},
            ],
        }

        response = self.client.post(
            "/api/report",
            data={
                "configuration": json.dumps(configuration),
                "gpx_files": [
                    (io.BytesIO(GPX), "zoe.gpx"),
                    (io.BytesIO(GPX), "amy.gpx"),
                ],
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "columns": ["user_name", "start", "elsewhere"],
                "rows": [
                    ["amy", "04:00:00", ""],
                    ["zoe", "04:00:00", ""],
                ],
                "warnings": [],
            },
        )

    def test_returns_missing_timestamp_warning(self) -> None:
        gpx_without_time = GPX.replace(
            b"<time>2026-07-01T01:00:00Z</time>",
            b"",
        )
        response = self.client.post(
            "/api/report",
            data={
                "configuration": json.dumps(
                    {
                        "timezone": "UTC",
                        "radius_m": 20,
                        "checkpoints": [
                            {"name": "start", "latitude": 47.0, "longitude": 28.0}
                        ],
                    }
                ),
                "gpx_files": (io.BytesIO(gpx_without_time), "amy.gpx"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("missing a timestamp", response.get_json()["warnings"][0])

    def test_rejects_invalid_requests(self) -> None:
        valid_configuration = {
            "timezone": "UTC",
            "radius_m": 20,
            "checkpoints": [
                {"name": "start", "latitude": 47.0, "longitude": 28.0}
            ],
        }
        cases = [
            ({}, "configuration"),
            (
                {"configuration": json.dumps(valid_configuration)},
                "GPX file",
            ),
            (
                {
                    "configuration": "{",
                    "gpx_files": (io.BytesIO(GPX), "amy.gpx"),
                },
                "valid JSON",
            ),
            (
                {
                    "configuration": json.dumps(valid_configuration),
                    "gpx_files": (io.BytesIO(b"text"), "notes.txt"),
                },
                ".gpx",
            ),
            (
                {
                    "configuration": json.dumps(valid_configuration),
                    "gpx_files": (io.BytesIO(GPX), "../amy.gpx"),
                },
                "path separators",
            ),
            (
                {
                    "configuration": json.dumps(
                        {**valid_configuration, "timezone": ""}
                    ),
                    "gpx_files": (io.BytesIO(GPX), "amy.gpx"),
                },
                "non-empty",
            ),
            (
                {
                    "configuration": json.dumps(
                        {**valid_configuration, "timezone": "Unknown/Nowhere"}
                    ),
                    "gpx_files": (io.BytesIO(GPX), "amy.gpx"),
                },
                "unknown timezone",
            ),
            (
                {
                    "configuration": json.dumps(
                        {**valid_configuration, "checkpoints": []}
                    ),
                    "gpx_files": (io.BytesIO(GPX), "amy.gpx"),
                },
                "checkpoints",
            ),
            (
                {
                    "configuration": json.dumps(
                        {**valid_configuration, "radius_m": 0}
                    ),
                    "gpx_files": (io.BytesIO(GPX), "amy.gpx"),
                },
                "greater than zero",
            ),
            (
                {
                    "configuration": json.dumps(
                        {**valid_configuration, "radius_m": "20"}
                    ),
                    "gpx_files": (io.BytesIO(GPX), "amy.gpx"),
                },
                "must be a number",
            ),
            (
                {
                    "configuration": json.dumps(
                        {
                            **valid_configuration,
                            "checkpoints": [
                                {"name": "", "latitude": 47.0, "longitude": 28.0}
                            ],
                        }
                    ),
                    "gpx_files": (io.BytesIO(GPX), "amy.gpx"),
                },
                "name must be non-empty",
            ),
            (
                {
                    "configuration": json.dumps(
                        {
                            **valid_configuration,
                            "checkpoints": [
                                {"name": "same", "latitude": 47.0, "longitude": 28.0},
                                {"name": "same", "latitude": 48.0, "longitude": 29.0},
                            ],
                        }
                    ),
                    "gpx_files": (io.BytesIO(GPX), "amy.gpx"),
                },
                "unique",
            ),
            (
                {
                    "configuration": json.dumps(
                        {
                            **valid_configuration,
                            "checkpoints": [
                                {"name": "bad", "latitude": 91.0, "longitude": 28.0}
                            ],
                        }
                    ),
                    "gpx_files": (io.BytesIO(GPX), "amy.gpx"),
                },
                "out of range",
            ),
            (
                {
                    "configuration": json.dumps(
                        {
                            **valid_configuration,
                            "checkpoints": [
                                {
                                    "name": "bad",
                                    "latitude": "47",
                                    "longitude": 28.0,
                                }
                            ],
                        }
                    ),
                    "gpx_files": (io.BytesIO(GPX), "amy.gpx"),
                },
                "latitude must be a number",
            ),
            (
                {
                    "configuration": json.dumps(
                        {
                            **valid_configuration,
                            "checkpoints": [
                                {"name": "bad", "latitude": 47.0, "longitude": 181.0}
                            ],
                        }
                    ),
                    "gpx_files": (io.BytesIO(GPX), "amy.gpx"),
                },
                "out of range",
            ),
            (
                {
                    "configuration": json.dumps(valid_configuration),
                    "gpx_files": [
                        (io.BytesIO(GPX), "amy.gpx"),
                        (io.BytesIO(GPX), "AMY.GPX"),
                    ],
                },
                "duplicate",
            ),
            (
                {
                    "configuration": json.dumps(valid_configuration),
                    "gpx_files": (io.BytesIO(b"<gpx>"), "amy.gpx"),
                },
                "malformed GPX",
            ),
        ]

        for data, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                response = self.client.post(
                    "/api/report",
                    data=data,
                    content_type="multipart/form-data",
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(expected_error, response.get_json()["error"])
```

- [ ] **Step 2: Run endpoint tests and verify RED**

Run:

```bash
bash -o pipefail -c 'rtk python3 -m unittest test_web_app \
  2>&1 | tail -c 2000'
```

Expected: import failure because `web_app.py` does not exist.

- [ ] **Step 3: Add Flask and implement the stateless endpoint**

Create `requirements.txt`:

```text
Flask>=3.1,<3.2
```

Create `web_app.py`:

```python
#!/usr/bin/env python3

from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stderr
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, request

from gpx_checkpoint_report import build_report_rows, load_config, parse_config


ROOT = Path(__file__).resolve().parent


def create_app(config_path: Optional[Path] = None) -> Flask:
    app = Flask(__name__)
    checkpoints_path = config_path or ROOT / "checkpoints.json"

    @app.errorhandler(ValueError)
    def handle_value_error(error: ValueError):
        return jsonify(error=str(error)), 400

    @app.get("/")
    def index():
        config = load_config(checkpoints_path)
        defaults = {
            "radius_m": config.radius_m,
            "checkpoints": [
                {
                    "name": checkpoint.name,
                    "latitude": checkpoint.latitude,
                    "longitude": checkpoint.longitude,
                }
                for checkpoint in config.checkpoints
            ],
        }
        return render_template("index.html", defaults=defaults)

    @app.post("/api/report")
    def report():
        raw_configuration = request.form.get("configuration")
        if raw_configuration is None:
            raise ValueError("configuration is required")
        try:
            configuration = json.loads(raw_configuration)
        except json.JSONDecodeError as error:
            raise ValueError("configuration must be valid JSON") from error
        config = parse_config(configuration, "configuration")

        uploads = [
            upload
            for upload in request.files.getlist("gpx_files")
            if upload.filename
        ]
        if not uploads:
            raise ValueError("at least one GPX file is required")

        filenames: set[str] = set()
        for upload in uploads:
            filename = upload.filename or ""
            if "/" in filename or "\\" in filename:
                raise ValueError("GPX filenames must not contain path separators")
            if not filename.lower().endswith(".gpx"):
                raise ValueError(f"{filename}: file must have a .gpx extension")
            normalized_filename = filename.casefold()
            if normalized_filename in filenames:
                raise ValueError(f"{filename}: duplicate GPX filename")
            filenames.add(normalized_filename)

        warnings = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            upload_paths = []
            for index, upload in enumerate(uploads):
                upload_directory = Path(directory) / str(index)
                upload_directory.mkdir()
                upload_path = upload_directory / (upload.filename or "")
                upload.save(upload_path)
                upload_paths.append(upload_path)

            with redirect_stderr(warnings):
                rows = build_report_rows(upload_paths, config)

        return jsonify(
            columns=rows[0],
            rows=rows[1:],
            warnings=[
                line.removeprefix("warning: ")
                for line in warnings.getvalue().splitlines()
                if line
            ],
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", debug=False)
```

- [ ] **Step 4: Install Flask if needed and run endpoint tests**

Run:

```bash
python3 -m pip install -r requirements.txt
bash -o pipefail -c 'rtk python3 -m unittest test_web_app \
  2>&1 | tail -c 3000'
```

Expected: all `test_web_app` tests pass.

- [ ] **Step 5: Commit the endpoint**

```bash
git add requirements.txt web_app.py test_web_app.py
git commit -m "FB_DEVOPS-0_fisakov add local report endpoint"
```

### Task 3: Add the interactive report page

**Files:**
- Create: `templates/index.html`
- Modify: `test_web_app.py`

**Interfaces:**
- Consumes: `defaults: {"radius_m": float, "checkpoints": list[dict[str, object]]}`
- Consumes: `POST /api/report` JSON response
- Produces: dynamic checkpoint controls, HTML report table, `report.csv`

- [ ] **Step 1: Tighten the page contract test**

Extend `test_home_page_contains_default_configuration`:

```python
        for expected_control in (
            b'id="timezone"',
            b'id="radius"',
            b'id="checkpoint-rows"',
            b'id="add-checkpoint"',
            b'id="gpx-files"',
            b'id="generate-report"',
            b'id="download-csv"',
        ):
            self.assertIn(expected_control, response.data)
```

- [ ] **Step 2: Run the page test and verify RED**

Run:

```bash
bash -o pipefail -c 'rtk python3 -m unittest \
  test_web_app.WebAppTests.test_home_page_contains_default_configuration \
  2>&1 | tail -c 2000'
```

Expected: failure because the template and required controls do not exist.

- [ ] **Step 3: Implement the single-page interface**

Create `templates/index.html` with:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GPX checkpoint report</title>
  <style>
    :root {
      color-scheme: light;
      font-family: system-ui, sans-serif;
      color: #172033;
      background: #f4f6fa;
    }
    body { margin: 0; }
    main { max-width: 1100px; margin: 0 auto; padding: 32px 20px 64px; }
    h1 { margin-top: 0; }
    section {
      margin-top: 24px;
      padding: 24px;
      border: 1px solid #d8deea;
      border-radius: 12px;
      background: white;
    }
    label { display: grid; gap: 6px; font-weight: 600; }
    input, button { font: inherit; }
    input {
      min-width: 0;
      padding: 9px 10px;
      border: 1px solid #aeb8ca;
      border-radius: 6px;
    }
    button {
      padding: 10px 14px;
      border: 0;
      border-radius: 6px;
      background: #2457d6;
      color: white;
      cursor: pointer;
    }
    button.secondary { background: #526176; }
    button.danger { background: #b42318; }
    button:disabled { opacity: .6; cursor: wait; }
    .settings { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; }
    .checkpoint-row {
      display: grid;
      grid-template-columns: 2fr 1fr 1fr auto;
      gap: 10px;
      align-items: end;
      margin-bottom: 10px;
    }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
    .message { margin-top: 16px; padding: 12px; border-radius: 6px; }
    .error { color: #7a271a; background: #fef3f2; }
    .warning { color: #7a2e0e; background: #fffaeb; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 10px; border: 1px solid #d8deea; text-align: left; }
    th { background: #eef2f8; }
    [hidden] { display: none !important; }
    @media (max-width: 720px) {
      .settings, .checkpoint-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main>
    <h1>GPX checkpoint report</h1>
    <p>Configure checkpoints, upload GPX tracks, and generate arrival times.</p>

    <form id="report-form">
      <section>
        <h2>Configuration</h2>
        <div class="settings">
          <label>
            Browser timezone
            <input id="timezone" readonly required>
          </label>
          <label>
            Checkpoint radius (metres)
            <input id="radius" type="number" min="0.01" step="any" required>
          </label>
        </div>

        <h3>Checkpoints</h3>
        <div id="checkpoint-rows"></div>
        <button id="add-checkpoint" class="secondary" type="button">
          Add new checkpoint
        </button>
      </section>

      <section>
        <h2>GPX files</h2>
        <label>
          Select one or more tracks
          <input id="gpx-files" type="file" accept=".gpx" multiple required>
        </label>
        <div class="actions">
          <button id="generate-report" type="submit">Generate report</button>
        </div>
        <div id="error" class="message error" role="alert" hidden></div>
      </section>
    </form>

    <section id="report-section" hidden>
      <h2>Report</h2>
      <div class="table-wrap"><table id="report-table"></table></div>
      <div id="warnings" class="message warning" hidden></div>
      <div class="actions">
        <button id="download-csv" type="button">Download CSV</button>
      </div>
    </section>
  </main>

  <script>
    const defaults = {{ defaults | tojson }};
    const rowsContainer = document.querySelector("#checkpoint-rows");
    const form = document.querySelector("#report-form");
    const errorBox = document.querySelector("#error");
    const reportSection = document.querySelector("#report-section");
    const reportTable = document.querySelector("#report-table");
    const warningsBox = document.querySelector("#warnings");
    const submitButton = document.querySelector("#generate-report");
    let reportData = null;

    document.querySelector("#timezone").value =
      Intl.DateTimeFormat().resolvedOptions().timeZone;
    document.querySelector("#radius").value = defaults.radius_m;

    function addCheckpoint(checkpoint = {}) {
      const row = document.createElement("div");
      row.className = "checkpoint-row";
      row.innerHTML = `
        <label>Name<input class="checkpoint-name" required></label>
        <label>Latitude<input class="checkpoint-latitude" type="number"
          min="-90" max="90" step="any" required></label>
        <label>Longitude<input class="checkpoint-longitude" type="number"
          min="-180" max="180" step="any" required></label>
        <button class="danger delete-checkpoint" type="button">Delete</button>
      `;
      row.querySelector(".checkpoint-name").value = checkpoint.name ?? "";
      row.querySelector(".checkpoint-latitude").value =
        checkpoint.latitude ?? "";
      row.querySelector(".checkpoint-longitude").value =
        checkpoint.longitude ?? "";
      row.querySelector(".delete-checkpoint").addEventListener(
        "click",
        () => row.remove(),
      );
      rowsContainer.append(row);
    }

    defaults.checkpoints.forEach(addCheckpoint);
    document.querySelector("#add-checkpoint").addEventListener(
      "click",
      () => addCheckpoint(),
    );

    function currentConfiguration() {
      return {
        timezone: document.querySelector("#timezone").value,
        radius_m: Number(document.querySelector("#radius").value),
        checkpoints: [...document.querySelectorAll(".checkpoint-row")].map(
          (row) => ({
            name: row.querySelector(".checkpoint-name").value,
            latitude: Number(row.querySelector(".checkpoint-latitude").value),
            longitude: Number(row.querySelector(".checkpoint-longitude").value),
          }),
        ),
      };
    }

    function renderReport(data) {
      reportTable.replaceChildren();
      const header = reportTable.createTHead().insertRow();
      data.columns.forEach((column) => {
        const cell = document.createElement("th");
        cell.scope = "col";
        cell.textContent = column;
        header.append(cell);
      });
      const body = reportTable.createTBody();
      data.rows.forEach((values) => {
        const row = body.insertRow();
        values.forEach((value) => {
          const cell = row.insertCell();
          cell.textContent = value;
        });
      });
      warningsBox.replaceChildren();
      if (data.warnings.length) {
        const list = document.createElement("ul");
        data.warnings.forEach((warning) => {
          const item = document.createElement("li");
          item.textContent = warning;
          list.append(item);
        });
        warningsBox.append(list);
        warningsBox.hidden = false;
      } else {
        warningsBox.hidden = true;
      }
      reportSection.hidden = false;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      errorBox.hidden = true;
      if (!rowsContainer.children.length) {
        errorBox.textContent = "Add at least one checkpoint.";
        errorBox.hidden = false;
        return;
      }
      const body = new FormData();
      body.append("configuration", JSON.stringify(currentConfiguration()));
      [...document.querySelector("#gpx-files").files].forEach(
        (file) => body.append("gpx_files", file),
      );
      submitButton.disabled = true;
      try {
        const response = await fetch("/api/report", { method: "POST", body });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "Unable to generate report.");
        }
        reportData = data;
        renderReport(data);
      } catch (error) {
        errorBox.textContent = error.message;
        errorBox.hidden = false;
      } finally {
        submitButton.disabled = false;
      }
    });

    function csvCell(value) {
      return `"${String(value).replaceAll('"', '""')}"`;
    }

    document.querySelector("#download-csv").addEventListener("click", () => {
      if (!reportData) return;
      const csv = [reportData.columns, ...reportData.rows]
        .map((row) => row.map(csvCell).join(","))
        .join("\r\n");
      const url = URL.createObjectURL(
        new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = "report.csv";
      link.click();
      URL.revokeObjectURL(url);
    });
  </script>
</body>
</html>
```

- [ ] **Step 4: Run the focused page and endpoint tests**

Run:

```bash
bash -o pipefail -c 'rtk python3 -m unittest test_web_app \
  2>&1 | tail -c 3000'
```

Expected: all web application tests pass.

- [ ] **Step 5: Commit the interface**

```bash
git add templates/index.html test_web_app.py
git commit -m "FB_DEVOPS-0_fisakov add interactive report page"
```

### Task 4: Document and verify the local workflow

**Files:**
- Modify: `README.md`

**Interfaces:**
- Documents: installation, startup, `http://127.0.0.1:5000`, report workflow

- [ ] **Step 1: Add a README contract test**

Add to `test_web_app.py`:

```python
    def test_readme_documents_web_application_startup(self) -> None:
        readme = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

        self.assertIn("python3 -m pip install -r requirements.txt", readme)
        self.assertIn("python3 web_app.py", readme)
        self.assertIn("http://127.0.0.1:5000", readme)
```

- [ ] **Step 2: Run the README test and verify RED**

Run:

```bash
bash -o pipefail -c 'rtk python3 -m unittest \
  test_web_app.WebAppTests.test_readme_documents_web_application_startup \
  2>&1 | tail -c 2000'
```

Expected: failure because the web instructions are absent.

- [ ] **Step 3: Add concise web instructions**

Append this section to `README.md`:

````markdown
## Local web application

Install Flask:

```bash
python3 -m pip install -r requirements.txt
```

Start the local server:

```bash
python3 web_app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). The page loads the
checkpoint defaults from `checkpoints.json` and uses your browser timezone.
Edit, add, or delete checkpoints; select one or more GPX files; then generate
the report. The displayed report can be downloaded as `report.csv`.
````

- [ ] **Step 4: Run focused automated verification**

Run:

```bash
bash -o pipefail -c 'rtk python3 -m unittest \
  test_gpx_checkpoint_report test_web_app 2>&1 | tail -c 4000'
```

Expected: all tests pass with no errors.

- [ ] **Step 5: Verify the browser workflow**

Start the application:

```bash
python3 web_app.py
```

Open `http://127.0.0.1:5000` and verify:

1. defaults load from `checkpoints.json`;
2. the detected timezone is visible;
3. checkpoint rows can be added and deleted independently;
4. the three repository GPX files generate a report;
5. validation errors do not remove the successful report; and
6. `Download CSV` produces `report.csv` with the same columns and rows.

- [ ] **Step 6: Commit documentation**

```bash
git add README.md test_web_app.py
git commit -m "FB_DEVOPS-0_fisakov document local web application"
```
