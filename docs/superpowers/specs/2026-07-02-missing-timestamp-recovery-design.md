# Missing Timestamp Recovery Design

## Goal

Produce the complete CSV report even when a track point reaches a checkpoint
but lacks a timestamp.

## Behavior

When a track point is within the configured radius of one or more pending
checkpoints but has no timestamp, the script:

1. prints a warning to standard error containing the GPX filename, one-based
   track-point number, and matched checkpoint names;
2. skips that track point without marking those checkpoints as reached;
3. continues searching later track points for a valid timestamp;
4. continues processing the remaining GPX files.

The warning uses the existing diagnostic format with a `warning:` prefix:

```text
warning: /path/Pavel Manoila.gpx: track point #471 reached checkpoint 'Грушевский родник' but is missing a timestamp
```

If a later point within the checkpoint radius has a timestamp, its converted
local time is written to the CSV. If no nearby point with a timestamp exists,
the checkpoint cell remains empty. Multiple malformed points produce separate
warnings so each source point remains identifiable.

Other invalid input remains fatal. This recovery applies only to a reached
track point with a missing timestamp.

## Implementation and Testing

The streaming parser will print the warning and continue to the next track
point instead of raising `ValueError`. Its function signature and return value
remain unchanged.

Tests will verify:

- a missing-timestamp point emits the detailed warning;
- a later valid point supplies the checkpoint time;
- multiple matched checkpoint names remain ordered in warnings;
- report generation continues to subsequent GPX files;
- an unrecoverable checkpoint produces an empty CSV cell.

Existing local changes to scripts, file modes, `checkpoints.json`, and GPX
files must be preserved.
