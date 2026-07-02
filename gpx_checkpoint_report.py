#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import math
import sys
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class Checkpoint:
    name: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Config:
    timezone: ZoneInfo
    radius_m: float
    checkpoints: tuple[Checkpoint, ...]


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def load_config(path: Path) -> Config:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: unable to read valid JSON configuration") from error
    return parse_config(data, str(path))


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
            raise ValueError(
                f"{source}: checkpoint {name} coordinates are out of range"
            )
        checkpoints.append(Checkpoint(name, latitude, longitude))
        names.add(name)

    return Config(timezone, radius_m, tuple(checkpoints))


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
    track_point_number = 0

    try:
        elements = ElementTree.iterparse(gpx_path, events=("end",))
        for _, element in elements:
            if _local_name(element.tag) != "trkpt":
                continue
            track_point_number += 1

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
                    checkpoint_label = (
                        "checkpoint" if len(reached) == 1 else "checkpoints"
                    )
                    checkpoint_names = ", ".join(
                        repr(checkpoint.name) for checkpoint in reached
                    )
                    print(
                        f"warning: {gpx_path}: track point "
                        f"#{track_point_number} reached "
                        f"{checkpoint_label} {checkpoint_names} "
                        "but is missing a timestamp",
                        file=sys.stderr,
                    )
                    element.clear()
                    continue
                local_time = _parse_time(time_element.text, gpx_path).astimezone(
                    timezone
                )
                for checkpoint in reached:
                    found[checkpoint.name] = local_time.strftime("%H:%M:%S")
                    del pending[checkpoint.name]
            element.clear()
    except ElementTree.ParseError as error:
        raise ValueError(f"{gpx_path}: malformed GPX XML") from error
    except OSError as error:
        raise ValueError(f"{gpx_path}: unable to read GPX file") from error

    return found


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


def main() -> int:
    try:
        generate_report(Path.cwd())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
