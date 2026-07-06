# Russian Web UI Design

## Goal

Present the web interface's static text in Russian and reduce initial form
clutter by collapsing checkpoint configuration until the user opens it.

## Scope

Translate static browser-facing text in `templates/index.html`, including the
document title, headings, descriptions, field labels, and buttons.

Do not translate:

- API validation errors;
- parser warnings;
- report column names or values;
- user-provided checkpoint names; or
- the downloaded CSV filename.

## Checkpoint Disclosure

Wrap the checkpoint heading, existing checkpoint rows, and add-checkpoint
button in a native HTML `details` element. Use a Russian `summary` label as the
control and leave the `open` attribute absent so the section starts collapsed.

Native disclosure behavior provides mouse and keyboard interaction without
additional JavaScript or manual ARIA state management. Existing checkpoint row
creation, editing, and deletion behavior remains unchanged.

## Testing

Extend the focused home-page rendering test to verify representative Russian
labels and the collapsed `details` structure. Existing API and report tests
remain unchanged because dynamic messages and report data are outside the
translation scope.
