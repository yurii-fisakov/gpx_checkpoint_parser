# Local GPX Checkpoint Web Application Design

## Goal

Add a locally hosted web interface where a user can configure checkpoints,
upload one or more GPX files, view the generated checkpoint report, and
download the same report as CSV.

The existing command-line workflow must continue to work.

## Scope

The web application will:

- run locally on the user's computer;
- load the initial radius and checkpoints from `checkpoints.json`;
- detect and use the browser's IANA timezone;
- allow the user to edit, add, and individually delete checkpoint rows;
- accept one or more `.gpx` files;
- render the report as an HTML table; and
- download the rendered report as a CSV file.

Authentication, public hosting, persistent user settings, report history, and
checkpoint map editing are out of scope.

## Architecture

Use Flask as a thin local HTTP server. The existing Python GPX parser remains
the source of truth for distance calculations, timestamp handling, and report
generation.

The development server binds to `127.0.0.1` with debug mode disabled so it is
reachable only from the same computer by default.

The server exposes:

- `GET /`, which renders the page with defaults loaded from
  `checkpoints.json`; and
- `POST /api/report`, which accepts multipart GPX uploads plus the current
  radius, browser timezone, and checkpoint configuration, then returns report
  columns, rows, and non-fatal warnings as JSON.

The server saves uploaded files only in a request-scoped temporary directory
and removes them after parsing. It does not retain reports or uploaded GPX
data.

The browser renders the returned rows as a table and creates the downloadable
CSV from that same result. This keeps the server stateless and guarantees that
the displayed and downloaded reports contain the same data.

## Components

### Shared report logic

Refactor only the narrow report-building boundary needed to let the CLI and
web endpoint supply an explicit configuration and ordered set of GPX paths.
Keep the existing parsing and checkpoint calculations unchanged. The CLI will
continue to discover GPX files in its working directory and write
`report.csv`.

### Flask application

The Flask application loads defaults from `checkpoints.json`, validates report
requests, manages temporary uploads, invokes the shared report logic, captures
non-fatal parser warnings, and serializes the result as JSON.

Flask is the only new runtime dependency.

### Browser interface

The page uses one HTML template with plain CSS and JavaScript. It contains:

- a read-only detected timezone field;
- an editable positive checkpoint radius;
- checkpoint rows with name, latitude, longitude, and a `Delete` button;
- an `Add new checkpoint` button that appends a blank row;
- a multiple-file `.gpx` picker;
- a `Generate report` button;
- an error area;
- a warning area;
- a report table; and
- a `Download CSV` button shown after successful generation.

There is no configured maximum checkpoint count. The user may delete every
row while editing, but at least one valid checkpoint is required to generate
a report.

## Data Flow

1. The browser requests `/`.
2. Flask loads `checkpoints.json` and embeds its radius and checkpoint rows in
   the page.
3. JavaScript obtains the browser timezone with
   `Intl.DateTimeFormat().resolvedOptions().timeZone`.
4. The user edits the configuration and selects GPX files.
5. JavaScript sends the current values and files to `/api/report` as
   `multipart/form-data`.
6. Flask validates the request and copies each upload into a temporary
   directory using a server-controlled path.
7. Shared Python report logic parses the files using their original filenames
   as rider names and returns ordered columns and rows.
8. Flask removes temporary files and returns JSON.
9. JavaScript renders the table and retains the result in memory for CSV
   download.

## Validation and Error Handling

Client-side validation provides immediate feedback, but the Flask endpoint is
authoritative.

The endpoint rejects:

- no uploaded files;
- a file whose name does not end in `.gpx`, case-insensitively;
- duplicate uploaded filenames;
- an empty or unknown timezone;
- a non-numeric, non-finite, or non-positive radius;
- no checkpoints;
- empty or duplicate checkpoint names;
- non-numeric or non-finite coordinates;
- latitude outside `-90` through `90`;
- longitude outside `-180` through `180`; and
- malformed or otherwise unreadable GPX data.

Validation and parsing errors return a clear message with a non-success HTTP
status. The browser displays the message and preserves any previous successful
report.

A checkpoint visit without a timestamp remains non-fatal. The parser skips
that visit, uses a later timestamped visit when available, and returns the
warning for display below the report.

## CSV Behavior

CSV columns retain the current format:

1. `user_name`;
2. one column per checkpoint, in the order shown in the form.

Rows are ordered by uploaded filename, matching the CLI's deterministic
ordering. The rider name is the original GPX filename without its final
`.gpx` extension. Empty cells represent checkpoints that were not reached.
The browser generates a UTF-8 CSV using standards-compliant quoting and
downloads it as `report.csv`.

## Testing

Keep the existing parser and CLI tests as regression coverage. Add focused
tests using Flask's test client for:

- loading defaults into the page;
- generating a report from multipart GPX uploads;
- applying a supplied browser timezone;
- accepting an arbitrary number of checkpoints;
- rejecting each server-side validation category;
- returning non-fatal missing-timestamp warnings; and
- returning report data that corresponds exactly to the expected CSV rows.

JavaScript remains limited to dynamic form rows, request submission, table
rendering, and CSV serialization. Verify the complete local workflow manually
in a browser after automated tests pass.

## Documentation

Update `README.md` with:

- dependency installation;
- the command to start the local Flask application;
- the local URL to open; and
- a concise description of configuring checkpoints, uploading files, viewing
  the table, and downloading `report.csv`.
