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
                        {"name": "default", "latitude": 47.0, "longitude": 28.0},
                        {
                            "name": "hidden default",
                            "latitude": 47.1,
                            "longitude": 28.1,
                            "hidden": True,
                            "color": "#999999",
                        },
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
        self.assertIn(b'"name": "hidden default"', response.data)
        self.assertIn(b'"hidden": true', response.data)
        self.assertIn(b'"color": "#999999"', response.data)
        self.assertIn(b'"radius_m": 20.0', response.data)
        self.assertIn("row.dataset.color = checkpoint.color", response.text)
        self.assertIn("applyReportNameColor", response.text)
        self.assertIn("currentColumnHiddenFlags", response.text)
        self.assertIn("applyReportHiddenStyle", response.text)
        self.assertIn("currentColumnMapLinks", response.text)
        self.assertIn("appendReportLink", response.text)
        self.assertIn("google.com/maps", response.text)
        self.assertNotIn("style.borderLeftColor", response.text)
        self.assertNotIn("row.style.borderLeftColor = checkpoint.color", response.text)
        for expected_control in (
            b'id="timezone"',
            b'id="radius"',
            b'id="checkpoint-rows"',
            b'id="hidden-checkpoint-rows"',
            b'id="add-checkpoint"',
            b'id="add-hidden-checkpoint"',
            b'id="gpx-files"',
            b'id="generate-report"',
            b'id="download-csv"',
        ):
            self.assertIn(expected_control, response.data)
        self.assertNotIn(b'class="checkpoint-color"', response.data)
        self.assertNotIn(b'class="checkpoint-map-link"', response.data)
        for expected_text in (
            "Отчёт по контрольным точкам GPX",
            "Настройки",
            "Часовой пояс браузера",
            "Контрольные точки",
            "Добавить контрольную точку",
            "Скрытые контрольные точки",
            "Добавить скрытую точку",
            "Файлы GPX",
            "Сформировать отчёт",
            "Скачать CSV",
        ):
            self.assertIn(expected_text, response.text)
        self.assertNotIn("Цвет", response.text)
        self.assertIn('<html lang="ru">', response.text)
        self.assertGreaterEqual(response.text.count("<details"), 2)
        self.assertNotIn("<details open", response.text)
        self.assertIn('class="info-icon"', response.text)
        self.assertIn('tabindex="0"', response.text)
        self.assertIn(
            "Расстояние, в пределах которого точка считается пройденной.",
            response.text,
        )
        self.assertIn(
            "Скрытые точки не показываются участникам маршрута",
            response.text,
        )

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
                "configuration": json.dumps(self._configuration()),
                "gpx_files": (io.BytesIO(gpx_without_time), "amy.gpx"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("missing a timestamp", response.get_json()["warnings"][0])

    def test_rejects_invalid_requests(self) -> None:
        valid_configuration = self._configuration()
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
                        {**valid_configuration, "checkpoints": []}
                    ),
                    "gpx_files": (io.BytesIO(GPX), "amy.gpx"),
                },
                "checkpoints",
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

    def test_readme_documents_web_application_startup(self) -> None:
        readme = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

        self.assertIn("python3 -m pip install -r requirements.txt", readme)
        self.assertIn("python3 web_app.py", readme)
        self.assertIn("http://127.0.0.1:5000", readme)

    @staticmethod
    def _configuration() -> dict:
        return {
            "timezone": "UTC",
            "radius_m": 20,
            "checkpoints": [
                {"name": "start", "latitude": 47.0, "longitude": 28.0}
            ],
        }


if __name__ == "__main__":
    unittest.main()
