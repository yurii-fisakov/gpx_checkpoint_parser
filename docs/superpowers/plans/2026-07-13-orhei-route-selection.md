# Orhei Route Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add route-aware CLI and web selection for Orhei 300 and Orhei 200, with route-specific checkpoint files and a clear missing-file error for the not-yet-provided Orhei 200 data.

**Architecture:** Keep route validation and checkpoint filename resolution in `gpx_checkpoint_report.py`. The web app uses that route vocabulary, exposes a small route-defaults endpoint, and keeps its existing client-side editable configuration/report API. Rename the current checkpoint data to `checkpoints_300.json`; do not add fabricated Orhei 200 coordinates.

**Tech Stack:** Python 3.9+, `argparse`, Flask, Jinja template JavaScript, `unittest`, Docker Compose.

## Global Constraints

- Route values are exactly the strings `300` and `200`.
- The CLI requires one positional route argument.
- Route `300` loads `checkpoints_300.json`; route `200` loads `checkpoints_200.json`.
- No fabricated Orhei 200 coordinates are added.
- Existing checkpoint editing and report generation remain available in the web UI.
- Preserve `create_app(config_path=...)` compatibility for tests and local callers.
- Every commit message starts with `FB_DEVOPS-0_fisakov`.

---

### Task 1: Add route-aware report generation and CLI validation

**Files:**
- Rename: `checkpoints.json` to `checkpoints_300.json`
- Modify: `gpx_checkpoint_report.py`
- Test: `test_gpx_checkpoint_report.py`

**Interfaces:**
- Produces `ROUTE_TYPES: tuple[str, ...] = ("300", "200")`.
- Produces `config_name_for_route(route: str) -> str`, returning
  `checkpoints_<route>.json` and raising `ValueError` for unsupported routes.
- Changes `generate_report(directory: Path, route: str = "300", output_name: str = "report.csv") -> Path` to load the route-specific file.
- Changes `main(argv: Optional[Sequence[str]] = None) -> int` to require the route positional argument.

- [ ] **Step 1: Write the failing route-generation test**

Add this test to `GpxCheckpointTests`:

```python
def test_generates_report_from_selected_route_configuration(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        runtime_directory = Path(directory)
        (runtime_directory / "checkpoints_200.json").write_text(
            json.dumps(
                {
                    "timezone": "UTC",
                    "radius_m": 20,
                    "checkpoints": [
                        {"name": "orhei_200", "latitude": 47.0, "longitude": 28.0}
                    ],
                }
            ),
            encoding="utf-8",
        )
        write_gpx(
            runtime_directory / "rider.gpx",
            [(47.0, 28.0, "2026-07-01T01:00:00Z")],
        )

        report_path = generate_report(runtime_directory, "200")

        with report_path.open(newline="", encoding="utf-8") as report:
            self.assertEqual(
                list(csv.reader(report)),
                [["user_name", "orhei_200"], ["rider", "01:00:00"]],
            )
```

Also add route validation tests:

```python
def test_rejects_unsupported_route(self) -> None:
    with self.assertRaisesRegex(ValueError, "route"):
        generate_report(Path("."), "100")

def test_cli_requires_a_supported_route(self) -> None:
    with self.assertRaises(SystemExit):
        main([])
    with self.assertRaises(SystemExit):
        main(["100"])
```

Import `main` and `Sequence` as needed; the CLI test only checks `argparse` validation, so it does not invoke report generation for invalid input.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```bash
python3 -m unittest test_gpx_checkpoint_report.GpxCheckpointTests.test_generates_report_from_selected_route_configuration test_gpx_checkpoint_report.GpxCheckpointTests.test_rejects_unsupported_route test_gpx_checkpoint_report.GpxCheckpointTests.test_cli_requires_a_supported_route -v
```

Expected: FAIL because route-specific generation, route validation, and the required CLI argument do not exist yet.

- [ ] **Step 3: Implement the minimal report-module changes**

Add the route constants/helper near the module constants:

```python
import argparse
from typing import Optional, Sequence

ROUTE_TYPES = ("300", "200")


def config_name_for_route(route: str) -> str:
    if route not in ROUTE_TYPES:
        raise ValueError(f"unsupported route {route!r}; expected 300 or 200")
    return f"checkpoints_{route}.json"
```

Change `generate_report` to call `load_config(directory / config_name_for_route(route))`, retaining the default route `"300"` for direct Python callers. Replace `main` with:

```python
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("route", choices=ROUTE_TYPES)
    arguments = parser.parse_args(argv)
    try:
        generate_report(Path.cwd(), arguments.route)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0
```

Rename the repository checkpoint file with `git mv checkpoints.json checkpoints_300.json`. Update existing temporary-file tests to create `checkpoints_300.json` where they exercise the default route.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run the same focused command. Expected: PASS, including both invalid CLI cases.

- [ ] **Step 5: Run the report test module**

Run:

```bash
python3 -m unittest test_gpx_checkpoint_report -v
```

Expected: all report tests pass.

- [ ] **Step 6: Commit the core change**

```bash
git add gpx_checkpoint_report.py test_gpx_checkpoint_report.py checkpoints_300.json
git commit -m "FB_DEVOPS-0_fisakov Add route-aware report CLI"
```

### Task 2: Add web route configuration loading

**Files:**
- Modify: `web_app.py`
- Test: `test_web_app.py`

**Interfaces:**
- `create_app(config_path: Optional[Path] = None) -> Flask` continues to work.
- Adds `GET /api/config/<route>`, returning JSON with `route`, `radius_m`, and `checkpoints`.
- A custom `config_path` is treated as route 300; route 200 resolves from the same directory as `config_path` using the filename `checkpoints_200.json`.

- [ ] **Step 1: Write failing web tests**

In `setUp`, create a sibling `checkpoints_200.json` with one distinct checkpoint. Add:

```python
def test_route_configuration_endpoint_loads_selected_route(self) -> None:
    response = self.client.get("/api/config/200")

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.get_json()["route"], "200")
    self.assertEqual(response.get_json()["checkpoints"][0]["name"], "orhei 200")

def test_route_configuration_endpoint_reports_missing_file(self) -> None:
    (self.config_path.parent / "checkpoints_200.json").unlink()

    response = self.client.get("/api/config/200")

    self.assertEqual(response.status_code, 400)
    self.assertIn("checkpoints_200.json", response.get_json()["error"])
```

- [ ] **Step 2: Run the focused web tests to verify they fail**

Run:

```bash
python3 -m unittest test_web_app.WebAppTests.test_route_configuration_endpoint_loads_selected_route test_web_app.WebAppTests.test_route_configuration_endpoint_reports_missing_file -v
```

Expected: FAIL because the route endpoint and route path resolution do not exist.

- [ ] **Step 3: Implement route path and configuration serialization**

Import `ROUTE_TYPES` and `config_name_for_route` from the report module. Build a route path mapping inside `create_app`:

```python
route_config_paths = {
    route: (
        config_path
        if route == "300" and config_path is not None
        else ROOT / config_name_for_route(route)
        if config_path is None
        else config_path.with_name(config_name_for_route(route))
    )
    for route in ROUTE_TYPES
}
```

Extract the existing checkpoint serialization into a local `configuration_defaults(route)` function that loads `route_config_paths[route]` and returns `route`, `radius_m`, and checkpoint dictionaries. Add:

```python
@app.get("/api/config/<route>")
def configuration(route: str):
    if route not in ROUTE_TYPES:
        raise ValueError("route must be 300 or 200")
    return jsonify(configuration_defaults(route))
```

Use `configuration_defaults("300")` in the existing index handler. Let missing or malformed files continue through the existing `ValueError` handler as HTTP 400.

- [ ] **Step 4: Run focused and existing web tests**

Run the two focused tests, then:

```bash
python3 -m unittest test_web_app -v
```

Expected: all web tests pass.

- [ ] **Step 5: Commit the web backend change**

```bash
git add web_app.py test_web_app.py
git commit -m "FB_DEVOPS-0_fisakov Add web route configuration endpoint"
```

### Task 3: Add the route selector to the web interface

**Files:**
- Modify: `templates/index.html`
- Test: `test_web_app.py`

**Interfaces:**
- Adds a `route` selector with values `300` and `200`.
- The browser calls `/api/config/<route>` when the selection changes.
- The existing report POST continues sending the currently edited configuration.

- [ ] **Step 1: Write the failing page assertions**

Extend `test_home_page_contains_default_configuration` with:

```python
for expected_control in (
    b'id="route"',
    b'<option value="300">Orhei 300</option>',
    b'<option value="200">Orhei 200</option>',
):
    self.assertIn(expected_control, response.data)
self.assertIn("/api/config/", response.text)
```

- [ ] **Step 2: Run the page test to verify it fails**

Run:

```bash
python3 -m unittest test_web_app.WebAppTests.test_home_page_contains_default_configuration -v
```

Expected: FAIL because the route control and route-loading JavaScript do not exist.

- [ ] **Step 3: Add the selector and route-loading behavior**

Add this label in the settings grid before the timezone label:

```html
<label>
  Маршрут
  <select id="route">
    <option value="300">Orhei 300</option>
    <option value="200">Orhei 200</option>
  </select>
</label>
```

Add these JavaScript functions and listeners after the existing DOM references:

```javascript
const routeSelect = document.querySelector("#route");
routeSelect.value = defaults.route;
let lastLoadedRoute = defaults.route;

function applyConfiguration(configuration) {
  document.querySelector("#radius").value = configuration.radius_m;
  rowsContainer.replaceChildren();
  hiddenRowsContainer.replaceChildren();
  configuration.checkpoints
    .filter((checkpoint) => !checkpoint.hidden)
    .forEach((checkpoint) => addCheckpoint(rowsContainer, checkpoint, false));
  configuration.checkpoints
    .filter((checkpoint) => checkpoint.hidden)
    .forEach((checkpoint) => addCheckpoint(hiddenRowsContainer, checkpoint, true));
}

routeSelect.addEventListener("change", async () => {
  const selectedRoute = routeSelect.options[routeSelect.selectedIndex].value;
  try {
    const response = await fetch(`/api/config/${selectedRoute}`);
    const configuration = await response.json();
    if (!response.ok) {
      throw new Error(configuration.error || "Не удалось загрузить маршрут.");
    }
    applyConfiguration(configuration);
    lastLoadedRoute = selectedRoute;
    reportSection.hidden = true;
  } catch (error) {
    routeSelect.value = lastLoadedRoute;
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  }
});
```

Initialize the page by calling `applyConfiguration(defaults)` instead of duplicating the current two `defaults.checkpoints.filter(...)` blocks. Keep `currentConfiguration()` unchanged because it already serializes the active edited rows.

- [ ] **Step 4: Run page and web integration tests**

Run:

```bash
python3 -m unittest test_web_app -v
```

Expected: all web tests pass, including route controls and existing report behavior.

- [ ] **Step 5: Commit the web UI change**

```bash
git add templates/index.html test_web_app.py
git commit -m "FB_DEVOPS-0_fisakov Add web route selector"
```

### Task 4: Update container packaging and documentation

**Files:**
- Modify: `Dockerfile`
- Modify: `compose.yaml`
- Modify: `README.md`
- Test: `test_web_app.py`

**Interfaces:**
- The image contains `checkpoints_300.json` and the application can load a later-added `checkpoints_200.json`.
- Compose mounts `checkpoints_300.json` read-only and documents the optional `checkpoints_200.json` mount for when that file is added.
- README documents both CLI invocations and route-specific web configuration.

- [ ] **Step 1: Add a failing documentation assertion**

Extend the README test with:

```python
self.assertIn("python3 gpx_checkpoint_report.py 300", readme)
self.assertIn("python3 gpx_checkpoint_report.py 200", readme)
self.assertIn("checkpoints_300.json", readme)
self.assertIn("checkpoints_200.json", readme)
```

- [ ] **Step 2: Run the focused documentation test to verify it fails**

Run:

```bash
python3 -m unittest test_web_app.WebAppTests.test_readme_documents_web_application_startup -v
```

Expected: FAIL until README documents the new route commands and files.

- [ ] **Step 3: Update packaging and documentation**

Change the Dockerfile copy list from `checkpoints.json` to `checkpoints_300.json`; do not copy a nonexistent Orhei 200 file. Change Compose to bind-mount `checkpoints_300.json` at `/app/checkpoints_300.json`. In README, document adding a second read-only mount for `checkpoints_200.json` after that file is added, so the current Compose setup remains runnable before the data exists. Update the native Docker command to mount `checkpoints_300.json`.

Update README configuration and CLI sections to use route-specific names and both commands. Explain that the web route selector loads the selected file and that `checkpoints_200.json` must be added before selecting Orhei 200.

- [ ] **Step 4: Run the documentation test and complete unit suite**

Run:

```bash
python3 -m unittest -v
```

Expected: all tests pass.

- [ ] **Step 5: Review diff and commit packaging/docs**

Run:

```bash
git diff HEAD~1 --check
git status --short
```

Confirm only the route-selection files and expected documentation/configuration changes are present, then commit:

```bash
git add Dockerfile compose.yaml README.md test_web_app.py
git commit -m "FB_DEVOPS-0_fisakov Document route-specific configuration"
```

## Plan Self-Review

- Spec coverage: CLI route argument and validation are covered by Task 1; route-specific files by Tasks 1 and 4; web selection and missing-file behavior by Tasks 2 and 3; compatibility and documentation by Tasks 2 and 4; tests are included in every task.
- Placeholder scan: no implementation step depends on an unspecified helper, file, or future coordinate data. The intentionally absent `checkpoints_200.json` is an explicit requirement, not an unfinished plan item.
- Type consistency: `ROUTE_TYPES`, `config_name_for_route`, `generate_report`, and `configuration_defaults` use the same route strings and filenames throughout.
