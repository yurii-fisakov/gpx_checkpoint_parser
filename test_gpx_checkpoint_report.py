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
