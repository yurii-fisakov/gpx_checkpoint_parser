# Orhei Route Selection Design

## Goal

Add support for the Orhei 200 route while preserving the existing Orhei 300
behavior. Route types are represented internally as the strings `300` and
`200`.

## Requirements

- The command-line entrypoint requires one positional route argument:
  `python3 gpx_checkpoint_report.py 300` or
  `python3 gpx_checkpoint_report.py 200`.
- Only `300` and `200` are valid route values.
- Route `300` loads `checkpoints_300.json`.
- Route `200` loads `checkpoints_200.json`.
- The existing `checkpoints.json` data becomes the Orhei 300 configuration.
- The web application lets the user choose Orhei 300 or Orhei 200.
- Selecting a route loads that route’s checkpoint defaults while preserving
  the existing ability to edit checkpoints before generating a report.
- No fabricated Orhei 200 coordinates are added. Until the user adds
  `checkpoints_200.json`, selecting Orhei 200 shows a clear configuration
  error.

## Design

The report module owns route validation and filename resolution through a
small route-to-config mapping. `generate_report` accepts a route and uses the
corresponding file. The CLI uses `argparse` with a required positional
argument and `choices=("300", "200")`, so invalid or missing values produce
standard usage errors before report generation.

The web app maps route values to configuration paths. Its initial page loads
the Orhei 300 defaults. A small configuration endpoint loads and returns the
defaults for a selected route. The browser route selector calls that endpoint,
rebuilds the editable checkpoint rows, and updates the radius. If a selected
route’s file is missing or invalid, the endpoint returns the existing JSON
error shape and the browser keeps the previous route selection.

The report API continues to accept the edited configuration, so route selection
changes the starting configuration without removing the current customization
workflow.

## Files and compatibility

- Rename `checkpoints.json` to `checkpoints_300.json`.
- Add route-aware behavior to `gpx_checkpoint_report.py`.
- Add route configuration loading and selector behavior to `web_app.py` and
  `templates/index.html`.
- Update Docker Compose, Docker image file copying, README examples, and
  tests to use `checkpoints_300.json`.
- Keep `create_app(config_path=...)` usable for tests and local callers by
  treating the supplied path as the route 300 configuration and resolving the
  route 200 file beside it.

## Testing

Add tests for:

- generating a report using a selected route-specific configuration;
- CLI acceptance of both routes and rejection of invalid or missing routes;
- web route options and loading route-specific defaults;
- a clear web error when the selected route configuration is absent.

Run the existing unit-test suite after the focused tests and inspect the final
diff/status before claiming completion.
