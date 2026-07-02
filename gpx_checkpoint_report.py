from __future__ import annotations

import math
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class Checkpoint:
    name: str
    latitude: float
    longitude: float


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

    try:
        elements = ElementTree.iterparse(gpx_path, events=("end",))
        for _, element in elements:
            if _local_name(element.tag) != "trkpt":
                continue

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
                    raise ValueError(
                        f"{gpx_path}: reached track point is missing a timestamp"
                    )
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
