import csv
import json
import tempfile
import unittest
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from gpx_checkpoint_report import (
    Checkpoint,
    find_checkpoint_times,
    generate_report,
    haversine_m,
    load_config,
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
