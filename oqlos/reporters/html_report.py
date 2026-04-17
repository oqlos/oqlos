"""OQLos HTML report renderer.

Pipeline:  data.json  →  raport.html

Produces a self-contained HTML file (embedded CSS + JS) that renders an OQL
test execution report.  The same ``data.json`` can also be consumed by the
frontend ``OqlReportRenderer`` React component.

Usage (CLI):
    oqlctl report data.json -o report.html

Usage (programmatic):
    from oqlos.reporters.html_report import render_html_report
    html = render_html_report(Path("data.json").read_text())
    Path("report.html").write_text(html)
"""

from __future__ import annotations

import json
from html import escape


def render_html_report(data_json: str) -> str:
    """Render a self-contained HTML report from an ``oqlos-report-v1`` JSON string."""
    data = json.loads(data_json)
    sc = data.get("scenario", {})
    meta = data.get("metadata", {})
    goals = data.get("goals", [])

    ok = sc.get("ok", False)
    status_class = "pass" if ok else "fail"
    status_text = "PASSED" if ok else "FAILED"

    goals_html = "\n".join(_render_goal(g, i) for i, g in enumerate(goals))

    errors_html = ""
    if data.get("errors"):
        items = "".join(f"<li>{escape(e)}</li>" for e in data["errors"])
        errors_html = f'<div class="errors"><h3>Errors</h3><ul>{items}</ul></div>'

    warnings_html = ""
    if data.get("warnings"):
        items = "".join(f"<li>{escape(w)}</li>" for w in data["warnings"])
        warnings_html = f'<div class="warnings"><h3>Warnings</h3><ul>{items}</ul></div>'

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OQL Report — {escape(sc.get('source', 'Scenario'))}</title>
{_CSS}
</head>
<body>
<div class="report">
  <header class="report-header">
    <div class="report-title">
      <h1>OQL Test Report</h1>
      <span class="badge {status_class}">{status_text}</span>
    </div>
    <div class="report-meta">
      <span>Source: <strong>{escape(sc.get('source', ''))}</strong></span>
      <span>Duration: <strong>{sc.get('duration_ms', 0):.0f} ms</strong></span>
      <span>Steps: <strong>{sc.get('passed', 0)}/{sc.get('total', 0)}</strong> passed</span>
      <span>Generated: <strong>{escape(data.get('generated_at', ''))}</strong></span>
    </div>
    {_render_device_meta(meta)}
  </header>

  <div class="goals-section">
    <h2>Goals ({len(goals)})</h2>
    {goals_html}
  </div>

  {errors_html}
  {warnings_html}

  <footer class="report-footer">
    <span>OQLos Report v1</span>
    <span>Pipeline: test.oql + .py → data.json → raport.html</span>
  </footer>
</div>
<script>
// Embed raw data.json for frontend re-render / export
window.__OQL_REPORT_DATA__ = {data_json};
</script>
</body>
</html>"""


def _render_device_meta(meta: dict) -> str:
    parts = []
    if meta.get("device_type"):
        parts.append(f"Type: <strong>{escape(meta['device_type'])}</strong>")
    if meta.get("device_model"):
        parts.append(f"Model: <strong>{escape(meta['device_model'])}</strong>")
    if meta.get("manufacturer"):
        parts.append(f"Manufacturer: <strong>{escape(meta['manufacturer'])}</strong>")
    if not parts:
        return ""
    spans = "".join(f"<span>{p}</span>" for p in parts)
    return f'<div class="report-device">{spans}</div>'


def _render_goal(goal: dict, idx: int) -> str:
    steps = goal.get("steps", [])
    thresholds = goal.get("thresholds", [])

    passed = sum(1 for s in steps if s.get("status") == "passed")
    failed = sum(1 for s in steps if s.get("status") in ("failed", "error"))
    total = len(steps)
    goal_ok = failed == 0 and total > 0
    cls = "pass" if goal_ok else ("fail" if failed else "pending")

    thresholds_html = _render_thresholds_table(thresholds) if thresholds else ""
    steps_html = "\n".join(_render_step(s, i) for i, s in enumerate(steps))

    return f"""
    <div class="goal {cls}">
      <div class="goal-header">
        <span class="goal-idx">{idx + 1}</span>
        <span class="goal-name">{escape(goal.get('name', 'Goal'))}</span>
        <span class="goal-stats">{passed}/{total} passed</span>
      </div>
      {thresholds_html}
      <div class="steps-table">
        <div class="steps-header">
          <span class="sh-idx">#</span>
          <span class="sh-name">Step</span>
          <span class="sh-status">Status</span>
          <span class="sh-val">Value</span>
          <span class="sh-time">Time</span>
          <span class="sh-msg">Message</span>
        </div>
        {steps_html}
      </div>
    </div>"""


def _render_thresholds_table(thresholds: list[dict]) -> str:
    rows = ""
    for t in thresholds:
        rows += f"""
        <tr>
          <td class="t-param">{escape(str(t.get('parameter', '')))}</td>
          <td class="t-unit">{escape(str(t.get('unit', '—')))}</td>
          <td class="t-min">{escape(str(t.get('min', '—')))}</td>
          <td class="t-max">{escape(str(t.get('max', '—')))}</td>
        </tr>"""
    return f"""
    <table class="thresholds-table">
      <thead><tr>
        <th>Parameter</th><th>Unit</th><th class="th-min">Min</th><th class="th-max">Max</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>"""


def _render_step(step: dict, idx: int) -> str:
    status = step.get("status", "pending")
    status_cls = {
        "passed": "pass", "failed": "fail", "error": "fail",
        "skipped": "skip", "warning": "warn", "pending": "pending",
    }.get(status, "pending")
    icon = {"passed": "✓", "failed": "✗", "error": "✗", "skipped": "—", "warning": "⚠"}.get(status, "·")

    val = step.get("value", "")
    if val is None:
        val = ""
    unit = step.get("unit", "")
    value_display = f"{val} {unit}".strip() if val else "—"

    msgs = []
    if step.get("message"):
        msgs.append(escape(step["message"]))
    if step.get("pass_message"):
        msgs.append(f'<span class="msg-pass">✓ {escape(step["pass_message"])}</span>')
    if step.get("fail_message"):
        msgs.append(f'<span class="msg-fail">✗ {escape(step["fail_message"])}</span>')
    msg_html = " ".join(msgs) if msgs else "—"

    return f"""
        <div class="step-row {status_cls}">
          <span class="s-idx">{idx + 1}</span>
          <span class="s-name">{escape(step.get('name', ''))}</span>
          <span class="s-status"><span class="status-icon">{icon}</span> {status}</span>
          <span class="s-val">{value_display}</span>
          <span class="s-time">{step.get('duration_ms', 0):.0f}ms</span>
          <span class="s-msg">{msg_html}</span>
        </div>"""


_CSS = """<style>
  :root {
    --bg: #0a0f1a; --bg-card: #111827; --border: #1e293b;
    --text: #e2e8f0; --text-muted: #64748b; --text-secondary: #94a3b8;
    --success: #10b981; --danger: #ef4444; --warning: #f59e0b; --info: #3b82f6;
    --font: 'Segoe UI', system-ui, sans-serif;
    --mono: 'JetBrains Mono', 'Fira Code', monospace;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.5; }
  .report { max-width: 960px; margin: 0 auto; padding: 24px 16px; }

  .report-header { margin-bottom: 24px; }
  .report-title { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
  .report-title h1 { font-size: 22px; font-weight: 700; }
  .badge { padding: 3px 12px; border-radius: 999px; font-size: 11px; font-weight: 700; text-transform: uppercase; }
  .badge.pass { background: rgba(16,185,129,0.15); color: var(--success); }
  .badge.fail { background: rgba(239,68,68,0.15); color: var(--danger); }
  .report-meta, .report-device { display: flex; gap: 16px; flex-wrap: wrap; font-size: 13px; color: var(--text-secondary); margin-top: 4px; }
  .report-device { margin-top: 6px; padding: 6px 0; border-top: 1px solid var(--border); }

  .goals-section h2 { font-size: 16px; margin-bottom: 12px; color: var(--text-muted); }

  .goal { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 16px; overflow: hidden; }
  .goal.pass { border-left: 3px solid var(--success); }
  .goal.fail { border-left: 3px solid var(--danger); }
  .goal.pending { border-left: 3px solid var(--text-muted); }
  .goal-header { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: rgba(30,41,59,0.4); border-bottom: 1px solid var(--border); }
  .goal-idx { display: inline-flex; align-items:center; justify-content:center; width:28px; height:28px; border-radius:50%; font-weight:700; font-size:13px; background:var(--border); }
  .goal.pass .goal-idx { background: rgba(16,185,129,0.2); color: var(--success); }
  .goal.fail .goal-idx { background: rgba(239,68,68,0.2); color: var(--danger); }
  .goal-name { font-weight: 600; flex: 1; }
  .goal-stats { font-size: 12px; color: var(--text-muted); font-family: var(--mono); }

  .thresholds-table { width: 100%; border-collapse: collapse; font-size: 12px; font-family: var(--mono); }
  .thresholds-table th { padding: 5px 12px; text-align: left; background: #1a1a2e; color: var(--text-muted); font-size: 10px; text-transform: uppercase; border-bottom: 1px solid #333; }
  .thresholds-table th.th-min, .thresholds-table th.th-max { text-align: right; }
  .thresholds-table td { padding: 6px 12px; border-bottom: 1px solid rgba(51,51,51,0.4); }
  .t-param { color: var(--text); }
  .t-unit { color: var(--text-muted); text-align: center; }
  .t-min { color: #38bdf8; text-align: right; }
  .t-max { color: #fb923c; text-align: right; }

  .steps-table { font-size: 12px; font-family: var(--mono); }
  .steps-header, .step-row { display: grid; grid-template-columns: 36px minmax(120px,1fr) 80px 80px 60px 1fr; padding: 5px 10px; border-bottom: 1px solid rgba(30,41,59,0.6); align-items: center; }
  .steps-header { background: rgba(30,41,59,0.6); font-weight: 700; color: var(--text-muted); font-size: 10px; text-transform: uppercase; }
  .step-row:hover { background: rgba(30,41,59,0.3); }
  .step-row.pass .s-status { color: var(--success); }
  .step-row.fail .s-status { color: var(--danger); }
  .step-row.skip .s-status { color: var(--warning); }
  .step-row.warn .s-status { color: var(--warning); }
  .s-idx { color: var(--text-muted); text-align: center; }
  .s-val { color: var(--text-secondary); text-align: right; }
  .s-time { color: var(--text-muted); text-align: right; }
  .s-msg { color: var(--text-secondary); font-size: 11px; }
  .msg-pass { color: var(--success); }
  .msg-fail { color: var(--danger); }

  .errors, .warnings { margin-top: 16px; padding: 12px; border-radius: 6px; }
  .errors { background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.2); }
  .errors h3 { color: var(--danger); font-size: 14px; margin-bottom: 6px; }
  .errors li { color: var(--danger); font-size: 12px; margin-left: 16px; }
  .warnings { background: rgba(245,158,11,0.08); border: 1px solid rgba(245,158,11,0.2); }
  .warnings h3 { color: var(--warning); font-size: 14px; margin-bottom: 6px; }
  .warnings li { color: var(--warning); font-size: 12px; margin-left: 16px; }

  .report-footer { margin-top: 32px; padding-top: 12px; border-top: 1px solid var(--border); display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); }

  @media (max-width: 700px) {
    .steps-header, .step-row { grid-template-columns: 30px 1fr 60px 60px 50px; }
    .s-msg { display: none; }
  }
</style>"""
