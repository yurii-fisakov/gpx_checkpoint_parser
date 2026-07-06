# Radius Tooltip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a compact Russian explanation beside the checkpoint radius label.

**Architecture:** Add a focusable inline information icon and a nested CSS-only tooltip to the existing template. Hover and focus selectors expose the same explanation without JavaScript.

**Tech Stack:** Flask/Jinja HTML, CSS, Python `unittest`

## Global Constraints

- Use the text `Расстояние, в пределах которого точка считается пройденной.`
- Show the tooltip on mouse hover and keyboard focus.
- Do not change radius input or form behavior.
- Preserve the existing uncommitted introductory-text edit.

---

### Task 1: Add the radius tooltip

**Files:**
- Modify: `test_web_app.py`
- Modify: `templates/index.html`

**Interfaces:**
- Consumes: the existing `GET /` page and `#radius` input.
- Produces: `.info-icon` and `.tooltip` elements adjacent to the radius label.

- [ ] **Step 1: Write the failing rendering assertions**

Add these assertions to
`test_home_page_contains_default_configuration`:

```python
        self.assertIn('class="info-icon"', response.text)
        self.assertIn('tabindex="0"', response.text)
        self.assertIn(
            "Расстояние, в пределах которого точка считается пройденной.",
            response.text,
        )
```

- [ ] **Step 2: Verify the test fails**

Run:

```bash
python3 -m unittest test_web_app.WebAppTests.test_home_page_contains_default_configuration
```

Expected: failure because `.info-icon` is absent.

- [ ] **Step 3: Add the tooltip markup and styles**

Replace the radius label text with:

```html
            <span class="label-text">
              Радиус контрольной точки (м)
              <span
                class="info-icon"
                role="img"
                tabindex="0"
                aria-label="Расстояние, в пределах которого точка считается пройденной."
              >
                ⓘ
                <span class="tooltip" aria-hidden="true">
                  Расстояние, в пределах которого точка считается пройденной.
                </span>
              </span>
            </span>
```

Add:

```css
    .label-text {
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .info-icon {
      position: relative;
      color: #526176;
      cursor: help;
      font-size: .9em;
      line-height: 1;
      outline-offset: 2px;
    }

    .tooltip {
      position: absolute;
      z-index: 1;
      bottom: calc(100% + 8px);
      left: 50%;
      width: 220px;
      padding: 8px 10px;
      border-radius: 6px;
      background: #172033;
      color: white;
      font-size: .85rem;
      font-weight: 400;
      line-height: 1.3;
      opacity: 0;
      pointer-events: none;
      transform: translateX(-50%);
      visibility: hidden;
    }

    .info-icon:hover .tooltip,
    .info-icon:focus .tooltip {
      opacity: 1;
      visibility: visible;
    }
```

- [ ] **Step 4: Verify the web interface**

Run:

```bash
python3 -m unittest test_web_app
```

Expected: all five web tests pass.

- [ ] **Step 5: Commit only tooltip changes**

Stage `test_web_app.py` and only the tooltip hunks from
`templates/index.html`, leaving the pre-existing introductory-text edit
unstaged. Commit:

```bash
git commit -m "FB_DEVOPS-0_fisakov explain checkpoint radius"
```
