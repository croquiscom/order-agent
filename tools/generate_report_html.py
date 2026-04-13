"""Generate HTML report from regression result JSON files.

Usage:
    # Latest result
    python3 -m tools.generate_report_html

    # Specific result file
    python3 -m tools.generate_report_html logs/regression_result_20260410_153000.json

    # Open in browser after generation
    python3 -m tools.generate_report_html --open
"""

from __future__ import annotations

import json
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = REPO_ROOT / "logs"
OUTPUT_DIR = REPO_ROOT / "logs"
JIRA_BASE_URL = "https://croquis.atlassian.net/browse"

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QA Report — {title}</title>
<style>
  :root {{
    --pass: #22c55e;
    --fail: #ef4444;
    --warn: #f59e0b;
    --bg: #0f172a;
    --surface: #1e293b;
    --surface2: #334155;
    --text: #e2e8f0;
    --text-dim: #94a3b8;
    --border: #475569;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 24px;
    line-height: 1.6;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 8px; }}
  .subtitle {{ color: var(--text-dim); font-size: 0.875rem; margin-bottom: 24px; }}

  /* Summary Cards */
  .summary {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
  }}
  .card {{
    background: var(--surface);
    border-radius: 12px;
    padding: 20px;
    border: 1px solid var(--border);
  }}
  .card-label {{ color: var(--text-dim); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .card-value {{ font-size: 2rem; font-weight: 700; margin-top: 4px; }}
  .card-value.pass {{ color: var(--pass); }}
  .card-value.fail {{ color: var(--fail); }}
  .card-value.neutral {{ color: var(--text); }}

  /* Progress Bar */
  .progress-bar {{
    height: 8px;
    background: var(--surface2);
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 32px;
  }}
  .progress-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s;
  }}
  .progress-fill.pass {{ background: var(--pass); }}
  .progress-fill.fail {{ background: var(--fail); }}

  /* Results Table */
  .section-title {{ font-size: 1.125rem; font-weight: 600; margin-bottom: 12px; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    background: var(--surface);
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 32px;
  }}
  th {{
    text-align: left;
    padding: 12px 16px;
    background: var(--surface2);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-dim);
    border-bottom: 1px solid var(--border);
  }}
  td {{
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    font-size: 0.875rem;
  }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover {{ background: var(--surface2); }}

  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
  }}
  .badge.pass {{ background: rgba(34,197,94,0.15); color: var(--pass); }}
  .badge.fail {{ background: rgba(239,68,68,0.15); color: var(--fail); }}

  a {{ color: #60a5fa; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .file-path {{ font-family: 'SF Mono', Monaco, Consolas, monospace; font-size: 0.8rem; }}
  .error-text {{ color: var(--fail); font-size: 0.8rem; font-family: monospace; }}
  .duration {{ color: var(--text-dim); }}

  /* Coverage Section */
  .coverage-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
  }}
  .coverage-card {{
    background: var(--surface);
    border-radius: 12px;
    padding: 16px;
    border: 1px solid var(--border);
  }}
  .coverage-card h3 {{ font-size: 0.9rem; margin-bottom: 8px; }}
  .coverage-bar {{
    display: flex;
    gap: 4px;
    margin-top: 8px;
  }}
  .coverage-segment {{
    height: 6px;
    border-radius: 3px;
    flex-grow: 1;
  }}

  /* Footer */
  .footer {{
    text-align: center;
    color: var(--text-dim);
    font-size: 0.75rem;
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid var(--border);
  }}

  /* Pool Status */
  .pool-status {{
    margin-bottom: 32px;
  }}
  .pool-item {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 0;
  }}
  .pool-label {{ min-width: 80px; font-weight: 500; }}
  .pool-bar {{
    flex: 1;
    height: 20px;
    background: var(--surface2);
    border-radius: 4px;
    overflow: hidden;
    position: relative;
  }}
  .pool-bar-fill {{
    height: 100%;
    border-radius: 4px;
  }}
  .pool-bar-fill.ok {{ background: var(--pass); }}
  .pool-bar-fill.low {{ background: var(--warn); }}
  .pool-bar-fill.empty {{ background: var(--fail); }}
  .pool-count {{ min-width: 60px; text-align: right; font-size: 0.85rem; color: var(--text-dim); }}

  /* Manual Steps */
  details {{ margin-top: 4px; }}
  details summary {{
    cursor: pointer;
    color: var(--text-dim);
    font-size: 0.75rem;
  }}
  details summary:hover {{ color: var(--text); }}
  .steps-list {{
    margin: 8px 0 4px 0;
    padding: 0;
    list-style: none;
    font-size: 0.8rem;
  }}
  .steps-list li {{
    padding: 3px 0;
    border-bottom: 1px solid var(--border);
    color: var(--text);
  }}
  .steps-list li:last-child {{ border-bottom: none; }}
  .steps-list .step-action {{
    color: var(--text-dim);
    font-family: monospace;
    font-size: 0.75rem;
  }}
</style>
</head>
<body>
<div class="container">
  <h1>{status_emoji} QA Report — {epic_header} — {status_text}</h1>
  <div class="subtitle">{timestamp} | Tier: {tier} | Area: {area}{tag_info} | Duration: {duration}s | Workers: {workers}</div>

  <!-- Summary Cards -->
  <div class="summary">
    <div class="card">
      <div class="card-label">Total</div>
      <div class="card-value neutral">{total}</div>
    </div>
    <div class="card">
      <div class="card-label">Passed</div>
      <div class="card-value pass">{passed}</div>
    </div>
    <div class="card">
      <div class="card-label">Failed</div>
      <div class="card-value {fail_class}">{failed}</div>
    </div>
    <div class="card">
      <div class="card-label">Pass Rate</div>
      <div class="card-value {rate_class}">{pass_rate}%</div>
    </div>
  </div>

  <!-- Progress Bar -->
  <div class="progress-bar">
    <div class="progress-fill pass" style="width: {pass_pct}%; float: left;"></div>
    <div class="progress-fill fail" style="width: {fail_pct}%; float: left;"></div>
  </div>

  {pool_section}

  {demand_section}

  {coverage_section}

  <!-- Results -->
  <div class="section-title">Scenario Results</div>
  <table>
    <thead>
      <tr>
        <th>Status</th>
        <th>Scenario</th>
        <th>Title</th>
        <th>Priority</th>
        <th>Area</th>
        <th>Duration</th>
        <th>Error</th>
      </tr>
    </thead>
    <tbody>
{result_rows}
    </tbody>
  </table>

  <div class="footer">
    Generated by order-agent QA Report | {generated_at}
  </div>
</div>
</body>
</html>
"""


def _jira_link(task_id: str) -> str:
    """Convert task ID (e.g. ORDER-11850) to clickable Jira link."""
    if not task_id or task_id == "-":
        return "-"
    return f'<a href="{JIRA_BASE_URL}/{task_id}" target="_blank" style="color:#60a5fa;text-decoration:none;">{task_id}</a>'


_PRECOND_LABELS = {
    "order_status": "주문 상태",
    "claim_type":   "클레임 유형",
    "product_type": "상품 유형",
    "payment":      "결제 방식",
    "special":      "특수 조건",
}


def _build_demand_section(scenario_demands: list[dict]) -> str:
    """Build required preconditions table grouped by condition type."""
    if not scenario_demands:
        return ""

    # Collect all condition keys
    all_keys: list[str] = []
    for d in scenario_demands:
        for k in (d.get("preconditions") or {}):
            if k not in all_keys:
                all_keys.append(k)
    # Sort: known keys first, then alphabetical
    known_order = list(_PRECOND_LABELS.keys())
    all_keys.sort(key=lambda k: (known_order.index(k) if k in known_order else 99, k))

    lines = [
        '<div class="section-title">Required Test Preconditions</div>',
        '<table>',
        '  <thead><tr><th>Scenario</th>',
    ]
    for k in all_keys:
        lines[-1] += f'<th>{_PRECOND_LABELS.get(k, k)}</th>'
    lines[-1] += '</tr></thead>'
    lines.append('  <tbody>')

    for d in scenario_demands:
        fname = d["file"].rsplit("/", 1)[-1].replace(".scn", "")
        precond = d.get("preconditions") or {}
        row = f'    <tr><td class="file-path">{fname}</td>'
        for k in all_keys:
            val = precond.get(k, "")
            row += f'<td>{val}</td>'
        row += '</tr>'
        lines.append(row)

    lines.append('  </tbody>')
    lines.append('</table>')
    return "\n".join(lines)


def _build_pool_section() -> str:
    """Build order pool status section."""
    try:
        from core.fixture_pool import OrderPool
        pool = OrderPool()
        status = pool.status()
        if not status:
            return ""
    except Exception:
        return ""

    lines = ['<div class="section-title">Order Pool Status</div>', '<div class="pool-status card">']
    for name, info in status.items():
        total = info["total"]
        available = info["available"]
        pct = (available / total * 100) if total > 0 else 0
        css = "ok" if pct > 50 else ("low" if pct > 0 else "empty")
        lines.append(f'  <div class="pool-item">')
        lines.append(f'    <span class="pool-label">{name}</span>')
        lines.append(f'    <div class="pool-bar"><div class="pool-bar-fill {css}" style="width:{pct}%"></div></div>')
        lines.append(f'    <span class="pool-count">{available}/{total}</span>')
        lines.append(f'  </div>')
    lines.append('</div>')
    return "\n".join(lines)


def _build_coverage_section(results: list[dict]) -> str:
    """Build area/tier coverage cards."""
    by_area: dict[str, dict] = {}
    for r in results:
        for area in (r.get("area") or []):
            if area not in by_area:
                by_area[area] = {"pass": 0, "fail": 0}
            if r["passed"]:
                by_area[area]["pass"] += 1
            else:
                by_area[area]["fail"] += 1

    if not by_area:
        return ""

    lines = ['<div class="section-title">Coverage by Area</div>', '<div class="coverage-grid">']
    for area in sorted(by_area.keys()):
        info = by_area[area]
        total = info["pass"] + info["fail"]
        pass_pct = info["pass"] / total * 100 if total > 0 else 0
        fail_pct = 100 - pass_pct
        lines.append(f'  <div class="coverage-card">')
        lines.append(f'    <h3>{area} ({info["pass"]}/{total})</h3>')
        lines.append(f'    <div class="coverage-bar">')
        if info["pass"] > 0:
            lines.append(f'      <div class="coverage-segment" style="flex:{info["pass"]};background:var(--pass)"></div>')
        if info["fail"] > 0:
            lines.append(f'      <div class="coverage-segment" style="flex:{info["fail"]};background:var(--fail)"></div>')
        lines.append(f'    </div>')
        lines.append(f'  </div>')
    lines.append('</div>')
    return "\n".join(lines)


def generate_html(report: dict) -> str:
    """Generate HTML from regression report dict."""
    results = report.get("results", [])
    total = report.get("total", len(results))
    passed = report.get("passed", sum(1 for r in results if r.get("passed")))
    failed = report.get("failed", total - passed)
    pass_rate = round(passed / total * 100, 1) if total > 0 else 0
    pass_pct = passed / total * 100 if total > 0 else 0
    fail_pct = 100 - pass_pct

    status_text = "PASS" if failed == 0 else "FAIL"
    status_emoji = "&#10004;" if failed == 0 else "&#10008;"
    fail_class = "fail" if failed > 0 else "pass"
    rate_class = "pass" if pass_rate >= 80 else ("fail" if pass_rate < 50 else "neutral")

    tag_info = ""
    if report.get("tag_filter"):
        tag_info = f" | Tags: {report['tag_filter']}"

    # Build result rows
    # Extract tasks for summary
    tasks = set()
    for r in results:
        if r.get("task"):
            tasks.add(r["task"])
    task_summary = ", ".join(sorted(tasks)) if tasks else "all"
    task_title = report.get("task_title") or ""

    # Build epic header: single Jira link + optional title
    if len(tasks) == 1:
        epic_id = next(iter(tasks))
        epic_header = _jira_link(epic_id)
        if task_title:
            epic_header += f" {task_title}"
    elif tasks:
        epic_header = ", ".join(_jira_link(t) for t in sorted(tasks))
        if task_title:
            epic_header += f" {task_title}"
    else:
        epic_header = task_title or "all"

    rows = []
    for r in results:
        status = "pass" if r["passed"] else "fail"
        label = "PASS" if r["passed"] else "FAIL"
        area_str = ", ".join(r.get("area") or ["-"])
        task_str = _jira_link(r.get("task") or "-")
        priority_str = r.get("priority") or "-"
        error_str = f'<span class="error-text">{r.get("error", "")}</span>' if r.get("error") else ""
        # Linked Jira issues
        linked = r.get("linked_issues") or []
        if linked:
            issue_links = " ".join(_jira_link(i) for i in linked)
            error_str = f"{error_str} {issue_links}" if error_str else issue_links

        # Manual steps expandable section
        steps = r.get("manual_steps") or []
        if steps:
            step_items = ""
            for s in steps:
                if s.startswith("  →"):
                    step_items += f'<li class="step-action">{s}</li>'
                else:
                    step_items += f'<li><strong>{s}</strong></li>'
            steps_html = (
                f'<details><summary>수동 테스트 가이드 ({len([s for s in steps if not s.startswith("  →")])} steps)</summary>'
                f'<ul class="steps-list">{step_items}</ul></details>'
            )
        else:
            steps_html = ""

        title_cell = r.get("title", "-") + steps_html

        rows.append(
            f'      <tr>\n'
            f'        <td><span class="badge {status}">{label}</span></td>\n'
            f'        <td class="file-path">{r.get("file", "")}</td>\n'
            f'        <td>{title_cell}</td>\n'
            f'        <td>{priority_str}</td>\n'
            f'        <td>{area_str}</td>\n'
            f'        <td class="duration">{r.get("duration_sec", 0)}s</td>\n'
            f'        <td>{error_str}</td>\n'
            f'      </tr>'
        )

    html = HTML_TEMPLATE.format(
        title=f"{task_summary} | {report.get('tier_filter', 'all')} {report.get('area_filter') or 'all'}",
        task_summary=task_summary,
        epic_header=epic_header,
        status_emoji=status_emoji,
        status_text=status_text,
        timestamp=report.get("timestamp", ""),
        tier=report.get("tier_filter", "all"),
        area=report.get("area_filter") or "all",
        tag_info=tag_info,
        duration=report.get("duration_sec", 0),
        workers=report.get("workers", 1),
        total=total,
        passed=passed,
        failed=failed,
        fail_class=fail_class,
        pass_rate=pass_rate,
        rate_class=rate_class,
        pass_pct=pass_pct,
        fail_pct=fail_pct,
        pool_section=_build_pool_section(),
        demand_section=_build_demand_section(report.get("scenario_demands", [])),
        coverage_section=_build_coverage_section(results),
        result_rows="\n".join(rows),
        generated_at=datetime.now().isoformat(timespec="seconds"),
    )

    return html


def find_latest_result() -> Path | None:
    """Find the most recent regression result JSON."""
    results = sorted(LOGS_DIR.glob("regression_result_*.json"), reverse=True)
    return results[0] if results else None


def main() -> int:
    open_browser = "--open" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--open"]

    if args:
        result_path = Path(args[0])
    else:
        result_path = find_latest_result()

    if not result_path or not result_path.exists():
        print("No regression result JSON found. Run regression first:")
        print("  python3 scripts/run_regression.py --tier smoke")
        return 1

    report = json.loads(result_path.read_text(encoding="utf-8"))
    html = generate_html(report)

    output_name = result_path.stem.replace("regression_result", "qa_report") + ".html"
    output_path = OUTPUT_DIR / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    print(f"Generated {output_path.relative_to(REPO_ROOT)} ({len(html)} bytes)")

    if open_browser:
        webbrowser.open(f"file://{output_path}")
        print("Opened in browser.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
