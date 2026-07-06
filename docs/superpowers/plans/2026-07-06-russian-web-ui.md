# Russian Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Translate static web-page text into Russian and place checkpoint editing in a collapsed disclosure control.

**Architecture:** Keep the existing single-template Flask interface and its JavaScript behavior. Use native HTML `details` and `summary` elements for disclosure, with focused CSS that makes the summary look actionable without adding JavaScript state.

**Tech Stack:** Flask, Jinja HTML template, plain CSS and JavaScript, Python `unittest`

## Global Constraints

- Translate only static browser-facing text in `templates/index.html`.
- Do not translate API errors, parser warnings, report data, user-provided names, or `report.csv`.
- Preserve existing checkpoint creation, editing, and deletion behavior.
- The checkpoint disclosure starts collapsed.

---

### Task 1: Translate and collapse the checkpoint interface

**Files:**
- Modify: `test_web_app.py`
- Modify: `templates/index.html`

**Interfaces:**
- Consumes: `GET /` rendered by `create_app()` and existing checkpoint DOM IDs/classes used by JavaScript.
- Produces: Russian static page copy and a collapsed native `details` element containing `#checkpoint-rows` and `#add-checkpoint`.

- [ ] **Step 1: Write the failing rendering test**

Extend `test_home_page_contains_default_configuration` after the existing
control assertions:

```python
        for expected_text in (
            "Отчёт по контрольным точкам GPX",
            "Настройки",
            "Часовой пояс браузера",
            "Контрольные точки",
            "Добавить контрольную точку",
            "Файлы GPX",
            "Сформировать отчёт",
            "Скачать CSV",
        ):
            self.assertIn(expected_text, response.text)
        self.assertIn('<html lang="ru">', response.text)
        self.assertIn("<details>", response.text)
        self.assertNotIn("<details open", response.text)
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
python -m unittest test_web_app.WebAppTests.test_home_page_contains_default_configuration
```

Expected: failure because the page still uses English copy and `lang="en"`.

- [ ] **Step 3: Implement the Russian static interface**

In `templates/index.html`:

- change the document language to `ru`;
- translate the title, heading, description, section headings, labels, and
  buttons into Russian;
- translate dynamic checkpoint-row labels and its delete button in the
  JavaScript template literal;
- wrap the checkpoint rows and add button with:

```html
        <details>
          <summary>Контрольные точки</summary>
          <div id="checkpoint-rows"></div>
          <button id="add-checkpoint" class="secondary" type="button">
            Добавить контрольную точку
          </button>
        </details>
```

- style `summary` as the existing secondary action and add bottom spacing only
  while the disclosure is open:

```css
    summary {
      width: fit-content;
      margin-top: 16px;
      padding: 10px 14px;
      border-radius: 6px;
      background: #526176;
      color: white;
      cursor: pointer;
      font-weight: 600;
    }

    details[open] summary {
      margin-bottom: 16px;
    }
```

- [ ] **Step 4: Run focused validation**

Run:

```bash
python -m unittest test_web_app.WebAppTests.test_home_page_contains_default_configuration
```

Expected: one passing test.

Then run:

```bash
python -m unittest test_web_app
```

Expected: all web application tests pass.

- [ ] **Step 5: Commit the implementation**

```bash
git add templates/index.html test_web_app.py
git commit -m "FB_DEVOPS-0_fisakov translate and collapse web UI"
```
