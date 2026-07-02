# Missing Timestamp Diagnostic Design

## Goal

Identify the exact GPX track point that matched a checkpoint but lacked a
timestamp.

## Behavior

Track points are numbered from 1 in GPX document order. If a track point is
within the configured radius of one or more pending checkpoints but has no
timestamp, the parser exits with an error containing:

- the GPX filename;
- the one-based track-point number;
- every matched checkpoint name.

Coordinates are intentionally omitted. A single-checkpoint error is formatted
as:

```text
Pavel Manoila.gpx: track point #471 reached checkpoint 'Грушевский родник' but is missing a timestamp
```

When one point matches multiple pending checkpoints, their names are shown in
configuration order.

## Implementation and Testing

The existing streaming parser will maintain a one-based counter for `<trkpt>`
elements and use the existing `reached` checkpoint list when constructing the
error. No parsing or report behavior changes otherwise.

The existing missing-timestamp test will assert the point number and checkpoint
name. A second assertion is unnecessary because the complete message proves
both values are included.

Existing local changes to the executable shebang, file modes,
`checkpoints.json`, and GPX files are outside this change and must be
preserved.
