#!/usr/bin/env python3

from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stderr
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, request

from gpx_checkpoint_report import (
    ROUTE_TYPES,
    build_report_rows,
    config_name_for_route,
    load_config,
    parse_config,
)


ROOT = Path(__file__).resolve().parent


def create_app(config_path: Optional[Path] = None) -> Flask:
    app = Flask(__name__)

    def route_config_path(route: str) -> Path:
        if route not in ROUTE_TYPES:
            raise ValueError("route must be 300 or 200")
        if config_path is not None:
            if route == "300":
                return config_path
            return config_path.with_name(config_name_for_route(route))
        return ROOT / config_name_for_route(route)

    def configuration_defaults(route: str) -> dict:
        config = load_config(route_config_path(route))
        return {
            "route": route,
            "radius_m": config.radius_m,
            "checkpoints": [
                {
                    "name": checkpoint.name,
                    "latitude": checkpoint.latitude,
                    "longitude": checkpoint.longitude,
                    "hidden": checkpoint.hidden,
                    "color": checkpoint.color,
                }
                for checkpoint in config.checkpoints
            ],
        }

    @app.errorhandler(ValueError)
    def handle_value_error(error: ValueError):
        return jsonify(error=str(error)), 400

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            defaults=configuration_defaults("300"),
        )

    @app.get("/api/config/<route>")
    def configuration(route: str):
        return jsonify(configuration_defaults(route))

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
