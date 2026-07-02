# README Report Table Design

## Goal

Present the generated report example as a rendered Markdown table instead of a
fenced CSV block.

## Change

Replace only the existing README CSV example with:

| user_name | Ставчены | Грушевский родник | Поворот на ВлВ | Круг ВлВ |
|---|---|---|---|---|
| Oleg Sat | 05:29:15 | 05:46:03 | 06:07:42 | 06:15:33 |
| Игорь Артемов | 07:06:41 | 07:25:29 | 07:57:11 | 08:09:36 |
| Юра Фисаков | 05:29:06 | 05:45:19 | 06:07:42 | 06:15:14 |

The table header and data cells must remain identical to the normalized values
in `report.csv`. No other README or application content changes.

Existing local script, test, configuration, file-mode, and GPX changes remain
untouched.

## Verification

Parse the Markdown table cells and compare them row-by-row with `report.csv`.
Also run `git diff --check` for the README change.
