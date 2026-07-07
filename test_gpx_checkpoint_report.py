import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from gpx_checkpoint_report import (
    Checkpoint,
    Config,
    build_report_rows,
    find_checkpoint_times,
    generate_report,
    haversine_m,
    load_config,
    parse_config,
)


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
    def test_parses_in_memory_configuration(self) -> None:
        config = parse_config(
            {
                "timezone": "Europe/Chisinau",
                "radius_m": 25,
                "checkpoints": [
                    {"name": "start", "latitude": 47.0, "longitude": 28.0},
                    {
                        "name": "secret",
                        "latitude": 47.1,
                        "longitude": 28.1,
                        "hidden": True,
                        "color": "#999999",
                    },
                ],
            }
        )

        self.assertEqual(config.timezone, ZoneInfo("Europe/Chisinau"))
        self.assertEqual(config.radius_m, 25.0)
        self.assertEqual(
            config.checkpoints,
            (
                Checkpoint("start", 47.0, 28.0, False),
                Checkpoint("secret", 47.1, 28.1, True, "#999999"),
            ),
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

    def test_report_continues_after_missing_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_directory = Path(directory)
            (runtime_directory / "checkpoints.json").write_text(
                json.dumps(
                    {
                        "timezone": "UTC",
                        "radius_m": 20,
                        "checkpoints": [
                            {
                                "name": "start",
                                "latitude": 47.0,
                                "longitude": 28.0,
                            }
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


if __name__ == "__main__":
    unittest.main()
