# GPX checkpoint report

Generate a CSV showing the first local time each rider came within a configured
distance of each checkpoint.

## Requirements

- Python 3.9 or newer
- GPX files containing timestamped track points, such as Strava exports

The command-line application has no third-party dependencies. The local web
application uses Flask.

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

| user_name | Ставчены | Грушевский родник | Поворот на ВлВ | Круг ВлВ |
| --- | --- | --- | --- | --- |
| Oleg Sat | 05:29:15 | 05:46:03 | 06:07:42 | 06:15:33 |
| Игорь Артемов | 07:06:41 | 07:25:29 | 07:57:11 | 08:09:36 |
| Юра Фисаков | 05:29:06 | 05:45:19 | 06:07:42 | 06:15:14 |

The user name is the GPX filename without `.gpx`. An empty checkpoint cell
means the track never came within `radius_m` of that checkpoint. If a track
enters the checkpoint radius more than once, only its first visit is reported.

## Local web application

Install Flask:

```bash
python3 -m pip install -r requirements.txt
```

Start the local server:

```bash
python3 web_app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). The page loads the
checkpoint defaults from `checkpoints.json` and uses your browser timezone.
Edit, add, or delete checkpoints; select one or more GPX files; then generate
the report. The displayed report can be downloaded as `report.csv`.
