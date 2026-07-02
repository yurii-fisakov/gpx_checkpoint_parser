# README Report Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the README report example as a standard Markdown table populated from the current `report.csv`.

**Architecture:** Replace only the existing fenced CSV block. A focused Python verifier parses the Markdown table and compares its cells row-by-row with the generated CSV.

**Tech Stack:** Markdown and Python 3 standard-library `csv`.

## Global Constraints

- Preserve every header and data value from `report.csv`.
- Change no README content outside the report example.
- Preserve existing local script, test, configuration, file-mode, and GPX changes.

---

### Task 1: Convert the report example to a Markdown table

**Files:**
- Modify: `README.md`
- Verify against: `report.csv`

**Interfaces:**
- Consumes: the current generated CSV report.
- Produces: a rendered Markdown table with matching cells.

- [ ] **Step 1: Replace the fenced CSV block**

Replace:

````text
```csv
user_name,Ставчены,Грушевский родник,Поворот на ВлВ,Круг ВлВ
Oleg Sat,05:29:15,05:46:03,06:07:42,06:15:33
Игорь Артемов,07:06:41,07:25:29,07:57:11,08:09:36
Юра Фисаков,05:29:06,05:45:19,06:07:42,06:15:14
```
````

with:

```markdown
| user_name | Ставчены | Грушевский родник | Поворот на ВлВ | Круг ВлВ |
| --- | --- | --- | --- | --- |
| Oleg Sat | 05:29:15 | 05:46:03 | 06:07:42 | 06:15:33 |
| Игорь Артемов | 07:06:41 | 07:25:29 | 07:57:11 | 08:09:36 |
| Юра Фисаков | 05:29:06 | 05:45:19 | 06:07:42 | 06:15:14 |
```

- [ ] **Step 2: Verify Markdown table cells against `report.csv`**

Run:

```bash
python3 - <<'PY'
import csv
from pathlib import Path

readme = Path("README.md").read_text(encoding="utf-8")
marker = "The script creates `report.csv`:\n\n"
start = readme.index(marker) + len(marker)
end = readme.index("\n\n", start)
table_lines = readme[start:end].splitlines()
table_rows = [
    [cell.strip() for cell in line.strip().strip("|").split("|")]
    for line in table_lines[:1] + table_lines[2:]
]
with Path("report.csv").open(newline="", encoding="utf-8") as report:
    report_rows = list(csv.reader(report))
assert table_rows == report_rows, (table_rows, report_rows)
print(f"README table matches report.csv: {len(report_rows) - 1} rider rows")
PY
```

Expected:

```text
README table matches report.csv: 3 rider rows
```

- [ ] **Step 3: Check README scope and whitespace**

Run:

```bash
git diff --check -- README.md
git diff -- README.md
```

Expected: only the CSV-to-table replacement and no whitespace errors.

- [ ] **Step 4: Commit only the README**

```bash
git add README.md
git commit -m "FB_DEVOPS-0_fisakov render README report as table"
```
