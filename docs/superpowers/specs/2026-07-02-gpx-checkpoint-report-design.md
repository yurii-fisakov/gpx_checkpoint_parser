# GPX Checkpoint Report Design

## Goal

Generate a CSV report showing the first time each rider came within a configured
distance of each checkpoint. Each rider is represented by a GPX file in the
runtime directory.

## Interface

The implementation will use Python's standard library and run as:

```text
python3 gpx_checkpoint_report.py
```

The script reads `checkpoints.json` and all files matching `*.gpx` from the
current working directory, then writes `report.csv` there.

The configuration structure is:

```json
{
  "timezone": "Europe/Chisinau",
  "radius_m": 20,
  "checkpoints": [
    {
      "name": "checkpoint_1",
      "latitude": 47.081821,
      "longitude": 28.769529
    }
  ]
}
```

Checkpoint order in the JSON array determines CSV column order. Checkpoint
names must be unique.

## Processing

For each GPX file, the script:

1. Uses the filename without the `.gpx` suffix as `user_name`.
2. Streams GPX track points in document order.
3. Calculates the Haversine distance from each track point to every checkpoint
   not already reached.
4. Records a checkpoint's timestamp when the first track point is within or
   exactly on the configured radius.
5. Converts that timestamp to the configured IANA timezone with `zoneinfo`.
6. Formats the result as `HH:MM:SS`.

The report contains one row per GPX file, ordered by filename. Its header is
`user_name` followed by the configured checkpoint names. An unreached
checkpoint produces an empty CSV cell.

## Error Handling

The script exits with a clear error when:

- the configuration is missing, malformed, or contains invalid values;
- a checkpoint name is duplicated;
- the configured timezone is unknown;
- a GPX file is malformed;
- a GPX track point is missing coordinates or has an invalid coordinate;
- a GPX track point that reaches a pending checkpoint has no valid timestamp;
- the report cannot be written.

Track points that do not reach a pending checkpoint do not require a timestamp.
GPX XML namespaces are handled by matching the standard GPX track-point and
time element names.

## Testing

Tests will use Python's built-in `unittest` and temporary directories. They
will cover:

- Haversine distance near the 20 m boundary;
- first visit selection when a rider passes a checkpoint multiple times;
- UTC-to-configured-timezone conversion and `HH:MM:SS` formatting;
- dynamic checkpoint headers and preserved checkpoint order;
- empty cells for unreached checkpoints;
- filename stems and deterministic file ordering;
- representative invalid configuration and GPX errors.

No third-party runtime or test dependencies are required.
