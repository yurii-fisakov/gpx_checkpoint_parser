# Missing Timestamp Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Warn and continue when a reached GPX track point has no timestamp, while still producing rows for all GPX files.

**Architecture:** Keep `find_checkpoint_times` and `generate_report` interfaces unchanged. Replace the missing-timestamp exception with a standard-error warning and continue the existing stream loop so later points can satisfy the checkpoint.

**Tech Stack:** Python 3.9+, standard-library `contextlib`, `csv`, `io`, and `unittest`.

## Global Constraints

- Retain the one-based track-point number and ordered checkpoint names in warnings.
- Leave a checkpoint pending after a missing-timestamp point.
- Use a later nearby timestamp when available; otherwise emit an empty CSV cell.
- Continue processing subsequent GPX files.
- Preserve existing local script, test, configuration, file-mode, and GPX changes.

---

### Task 1: Warn and recover from missing timestamps

**Files:**
- Modify: `test_gpx_checkpoint_report.py`
- Modify: `gpx_checkpoint_report.py`

**Interfaces:**
- Consumes: existing `find_checkpoint_times(...)` and `generate_report(...)`.
- Produces: unchanged return values plus detailed warnings on standard error.

- [ ] **Step 1: Replace exception assertions with recovery tests**

Add imports:

```python
import io
from contextlib import redirect_stderr
```

Replace `test_rejects_reached_track_point_without_time` with:

```python
def test_warns_and_uses_later_timestamp(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        gpx_path = Path(directory) / "rider.gpx"
        write_gpx(
            gpx_path,
            [
                (47.0, 28.0, None),
                (47.0, 28.0, "2026-07-01T01:00:00Z"),
            ],
        )
        warnings = io.StringIO()

        with redirect_stderr(warnings):
            result = find_checkpoint_times(
                gpx_path,
                (Checkpoint("start", 47.0, 28.0),),
                20.0,
                ZoneInfo("UTC"),
            )

    self.assertEqual(result, {"start": "01:00:00"})
    self.assertIn(
        "warning: "
        f"{gpx_path}: track point #1 reached checkpoint 'start' "
        "but is missing a timestamp",
        warnings.getvalue(),
    )
```

Replace `test_missing_timestamp_lists_reached_checkpoints_in_order` with:

```python
def test_missing_timestamp_warns_with_ordered_checkpoint_names(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        gpx_path = Path(directory) / "rider.gpx"
        write_gpx(gpx_path, [(47.0, 28.0, None)])
        warnings = io.StringIO()

        with redirect_stderr(warnings):
            result = find_checkpoint_times(
                gpx_path,
                (
                    Checkpoint("first", 47.0, 28.0),
                    Checkpoint("second", 47.0, 28.0),
                ),
                20.0,
                ZoneInfo("UTC"),
            )

    self.assertEqual(result, {})
    self.assertIn(
        "track point #1 reached checkpoints 'first', 'second' "
        "but is missing a timestamp",
        warnings.getvalue(),
    )
```

- [ ] **Step 2: Add a failing multi-file report test**

Add:

```python
def test_report_continues_after_missing_timestamp(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        runtime_directory = Path(directory)
        (runtime_directory / "checkpoints.json").write_text(
            json.dumps(
                {
                    "timezone": "UTC",
                    "radius_m": 20,
                    "checkpoints": [
                        {"name": "start", "latitude": 47.0, "longitude": 28.0}
                    ],
                }
            ),
            encoding="utf-8",
        )
        write_gpx(
            runtime_directory / "a_missing.gpx",
            [(47.0, 28.0, None)],
        )
        write_gpx(
            runtime_directory / "b_valid.gpx",
            [(47.0, 28.0, "2026-07-01T01:00:00Z")],
        )
        warnings = io.StringIO()

        with redirect_stderr(warnings):
            report_path = generate_report(runtime_directory)

        with report_path.open(newline="", encoding="utf-8") as report:
            rows = list(csv.reader(report))

    self.assertEqual(
        rows,
        [
            ["user_name", "start"],
            ["a_missing", ""],
            ["b_valid", "01:00:00"],
        ],
    )
    self.assertIn("a_missing.gpx: track point #1", warnings.getvalue())
```

- [ ] **Step 3: Run recovery tests and verify the old exception fails them**

Run:

```bash
python3 -m unittest \
  test_gpx_checkpoint_report.GpxCheckpointTests.test_warns_and_uses_later_timestamp \
  test_gpx_checkpoint_report.GpxCheckpointTests.test_missing_timestamp_warns_with_ordered_checkpoint_names \
  test_gpx_checkpoint_report.GpxCheckpointTests.test_report_continues_after_missing_timestamp
```

Expected: three errors because `find_checkpoint_times` still raises
`ValueError`.

- [ ] **Step 4: Replace the exception with a warning and continue**

Replace the missing-timestamp `raise ValueError(...)` block with:

```python
print(
    f"warning: {gpx_path}: track point #{track_point_number} reached "
    f"{checkpoint_label} {checkpoint_names} "
    "but is missing a timestamp",
    file=sys.stderr,
)
element.clear()
continue
```

This keeps the reached checkpoints in `pending`, allowing later track points
to supply their first valid timestamp.

- [ ] **Step 5: Run all tests**

Run:

```bash
python3 -m unittest -v
```

Expected: `Ran 8 tests` and `OK`.

- [ ] **Step 6: Verify real multi-file execution**

Run the CLI while preserving its exit status:

```bash
output="$(mktemp)"
./gpx_checkpoint_report.py >"$output" 2>&1
command_status=$?
head -c 4000 "$output"
rm -f "$output"
exit "$command_status"
```

Expected: exit code `0`, one or more detailed warnings if real GPX files
contain missing timestamps, and a generated `report.csv` containing one row
per `*.gpx` file.

- [ ] **Step 7: Leave overlapping implementation files unstaged**

Do not commit `gpx_checkpoint_report.py` or `test_gpx_checkpoint_report.py`
automatically because they contain pre-existing user-owned changes. Verify and
report the combined working-tree diff.
