# Missing Timestamp Diagnostic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Include the one-based GPX track-point number and matched checkpoint names in missing-timestamp errors.

**Architecture:** Extend the existing streaming loop with a track-point counter. Reuse the existing ordered `reached` list to construct singular or plural checkpoint context without changing parser interfaces.

**Tech Stack:** Python 3.9+, standard-library `unittest` and `xml.etree.ElementTree`.

## Global Constraints

- Omit coordinates from the error.
- Number only `<trkpt>` elements, starting at 1 in GPX document order.
- List every matched checkpoint in configuration order.
- Preserve all existing local changes to scripts, configuration, file modes, and GPX files.

---

### Task 1: Add exact missing-timestamp context

**Files:**
- Modify: `test_gpx_checkpoint_report.py`
- Modify: `gpx_checkpoint_report.py`

**Interfaces:**
- Consumes: existing `find_checkpoint_times(gpx_path, checkpoints, radius_m, timezone)`.
- Produces: unchanged function signature with richer `ValueError` messages.

- [ ] **Step 1: Tighten the existing test and add plural-checkpoint coverage**

Change the existing assertion to:

```python
with self.assertRaisesRegex(
    ValueError,
    r"rider\.gpx: track point #1 reached checkpoint 'start' "
    "but is missing a timestamp",
):
    find_checkpoint_times(
        gpx_path,
        (Checkpoint("start", 47.0, 28.0),),
        20.0,
        ZoneInfo("UTC"),
    )
```

Add this test:

```python
def test_missing_timestamp_lists_reached_checkpoints_in_order(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        gpx_path = Path(directory) / "rider.gpx"
        write_gpx(gpx_path, [(47.0, 28.0, None)])

        with self.assertRaisesRegex(
            ValueError,
            "track point #1 reached checkpoints 'first', 'second' "
            "but is missing a timestamp",
        ):
            find_checkpoint_times(
                gpx_path,
                (
                    Checkpoint("first", 47.0, 28.0),
                    Checkpoint("second", 47.0, 28.0),
                ),
                20.0,
                ZoneInfo("UTC"),
            )
```

- [ ] **Step 2: Run the focused tests and verify both fail for the old message**

Run:

```bash
python3 -m unittest \
  test_gpx_checkpoint_report.GpxCheckpointTests.test_rejects_reached_track_point_without_time \
  test_gpx_checkpoint_report.GpxCheckpointTests.test_missing_timestamp_lists_reached_checkpoints_in_order
```

Expected: two failures showing the old `reached track point is missing a
timestamp` message lacks point and checkpoint context.

- [ ] **Step 3: Add the track-point counter and contextual message**

Before the `iterparse` loop, initialize:

```python
track_point_number = 0
```

Immediately after confirming an element is a `<trkpt>`, increment:

```python
track_point_number += 1
```

Replace the missing-timestamp error with:

```python
checkpoint_label = "checkpoint" if len(reached) == 1 else "checkpoints"
checkpoint_names = ", ".join(repr(checkpoint.name) for checkpoint in reached)
raise ValueError(
    f"{gpx_path}: track point #{track_point_number} reached "
    f"{checkpoint_label} {checkpoint_names} but is missing a timestamp"
)
```

- [ ] **Step 4: Run all tests and verify they pass**

Run:

```bash
python3 -m unittest -v
```

Expected: `Ran 7 tests` and `OK`.

- [ ] **Step 5: Reproduce the reported Pavel Manoila diagnostic**

Run:

```bash
./gpx_checkpoint_report.py
```

Expected error:

```text
error: /Users/yfisakov/git/gpx_checkpoint_parser/Pavel Manoila.gpx: track point #471 reached checkpoint 'Грушевский родник' but is missing a timestamp
```

- [ ] **Step 6: Leave overlapping implementation files unstaged**

Do not commit `gpx_checkpoint_report.py` or `test_gpx_checkpoint_report.py`
automatically because both already contain user-owned local changes. Report
the verified diff so the user can commit the combined files intentionally.
