# GPX checkpoint report

Generate a CSV showing the first local time each rider came within a configured
distance of each checkpoint.

## Requirements

- Python 3.9 or newer
- GPX files containing timestamped track points, such as Strava exports

The command-line application has no third-party dependencies. The local web
application uses Flask.

## Configure

Edit `checkpoints_300.json` for Orhei 300. Add `checkpoints_200.json` with the
same structure when the Orhei 200 checkpoint coordinates are available:

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

Put the route checkpoint file, the script, and one or more `*.gpx` files in the
same directory, then provide the route type:

```bash
python3 gpx_checkpoint_report.py 300
python3 gpx_checkpoint_report.py 200
```

The `300` command loads `checkpoints_300.json`; the `200` command loads
`checkpoints_200.json`.

The script creates `report.csv`:

| user_name | Ставчены | Грушевский родник | Поворот на ВлВ | Круг ВлВ |
| --- | --- | --- | --- | --- |
| Oleg Sat | 05:29:15 | 05:46:03 | 06:07:42 | 06:15:33 |
| Игорь Артемов | 07:06:41 | 07:25:29 | 07:57:11 | 08:09:36 |
| Юра Фисаков | 05:29:06 | 05:45:19 | 06:07:42 | 06:15:14 |

The user name is the GPX filename without `.gpx`. An empty checkpoint cell
means the track never came within `radius_m` of that checkpoint. If a track
enters the checkpoint radius more than once, only its first visit is reported.

## Docker web application

Start the service with Docker Compose:

```bash
docker compose up --build
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Compose mounts the local
`checkpoints_300.json` read-only, so changes to the Orhei 300 defaults do not
require rebuilding the image. Add a second read-only mount for
`checkpoints_200.json` after adding that file if the Orhei 200 route should be
available in the container. Stop the service with `docker compose down`.

To run without Compose:

```bash
docker build -t gpx-checkpoint-report .
docker run --rm \
  -p 127.0.0.1:5000:8000 \
  --read-only \
  --tmpfs /tmp \
  -v "$PWD/checkpoints_300.json:/app/checkpoints_300.json:ro" \
  gpx-checkpoint-report
```

Add this volume to the command after creating the Orhei 200 file:

```bash
-v "$PWD/checkpoints_200.json:/app/checkpoints_200.json:ro" \
```

The container stores uploaded GPX files only in temporary memory and does not
persist reports.

## Native web application

Install Flask:

```bash
python3 -m pip install -r requirements.txt
```

Start the local server:

```bash
python3 web_app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). The page starts with
`checkpoints_300.json`, lets you select Orhei 300 or Orhei 200, and uses your
browser timezone. Edit, add, or delete checkpoints; select one or more GPX
files; then generate the report. Selecting Orhei 200 before
`checkpoints_200.json` exists shows a configuration error. The displayed report
can be downloaded as `report.csv`.
