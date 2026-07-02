# README Report Example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stale README CSV example with the complete current `report.csv`.

**Architecture:** This is a documentation-only replacement in the existing output section. A focused Python verifier will extract the fenced CSV block and compare normalized lines against `report.csv`.

**Tech Stack:** Markdown and Python 3 standard library.

## Global Constraints

- Change only the README CSV output example.
- Copy every header and rider row from the current `report.csv`.
- Preserve existing local script, test, configuration, file-mode, and GPX changes.

---

### Task 1: Synchronize the README output example

**Files:**
- Modify: `README.md`
- Verify against: `report.csv`

**Interfaces:**
- Consumes: the current generated CSV report.
- Produces: a README fenced CSV block with identical normalized lines.

- [ ] **Step 1: Replace the existing CSV block**

Replace:

```csv
user_name,checkpoint_1
Yurii_fisakov,04:14:09
```

with:

```csv
user_name,Ставчены,Грушевский родник,Поворот на ВлВ,Круг ВлВ
Oleg Sat,05:29:15,05:46:03,06:07:42,06:15:33
Игорь Артемов,07:06:41,07:25:29,07:57:11,08:09:36
Юра Фисаков,05:29:06,05:45:19,06:07:42,06:15:14
```

- [ ] **Step 2: Compare the README block with the generated report**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

readme = Path("README.md").read_text(encoding="utf-8")
marker = "The script creates `report.csv`:\n\n```csv\n"
start = readme.index(marker) + len(marker)
end = readme.index("\n```", start)
readme_lines = readme[start:end].splitlines()
report_lines = Path("report.csv").read_text(encoding="utf-8").splitlines()
assert readme_lines == report_lines, (readme_lines, report_lines)
print(f"README example matches report.csv: {len(report_lines) - 1} rider rows")
PY
```

Expected:

```text
README example matches report.csv: 3 rider rows
```

- [ ] **Step 3: Check whitespace and working-tree scope**

Run:

```bash
git diff --check -- README.md
git status --short
```

Expected: no README whitespace errors. Existing unrelated local changes remain
present and unstaged.

- [ ] **Step 4: Commit only the README**

```bash
git add README.md
git commit -m "FB_DEVOPS-0_fisakov update README report example"
```
