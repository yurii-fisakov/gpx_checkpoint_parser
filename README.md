# GPX checkpoint report

Generate a CSV showing the first local time each rider came within a configured
distance of each checkpoint.

## Requirements

- Python 3.9 or newer
- GPX files containing timestamped track points, such as Strava exports

No third-party packages are required.

## Configure

Edit `checkpoints.json`:

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

Checkpoint names become CSV columns in the same order. Use an
[IANA timezone name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

## Run

Put `checkpoints.json`, the script, and one or more `*.gpx` files in the same
directory, then run:

```bash
python3 gpx_checkpoint_report.py
```

The script creates `report.csv`:

```csv
user_name,checkpoint_1
Yurii_fisakov,04:14:09
```

The user name is the GPX filename without `.gpx`. An empty checkpoint cell
means the track never came within `radius_m` of that checkpoint. If a track
enters the checkpoint radius more than once, only its first visit is reported.
