"""Generate HTML QA report from team QA sheet CSV.

Structure: User Story → AC → Automation (3-tier)

Usage:
    python3 -m tools.generate_report_from_csv "path/to/qa_sheet.csv"
    python3 -m tools.generate_report_from_csv "path/to/qa_sheet.csv" --open
"""

from __future__ import annotations

import csv
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "logs"
JIRA_BASE_URL = "https://croquis.atlassian.net/browse"


def _jira_link(ticket_id: str, label: str | None = None) -> str:
    if not ticket_id:
        return ""
    text = label or ticket_id
    return f'<a href="{JIRA_BASE_URL}/{ticket_id}" target="_blank">{text}</a>'



def _extract_manual_steps(path: Path) -> list[str]:
    """Extract human-readable manual test guide from .scn file.

    Captures:
    - ``# ── N) description ──`` flow steps
    - ``# ── ACn: description ──`` verification steps
    - Key actions converted to human-readable instructions
    """
    import re
    steps: list[str] = []
    flow_re = re.compile(r"^#\s*──\s*(.+?)\s*──\s*$")
    num_re = re.compile(r"^#\s*\d+\)")

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("# @"):
            continue

        # ── N) ... ── or ── ACn: ... ── structured comments
        m = flow_re.match(line)
        if m:
            desc = m.group(1).strip()
            if re.match(r"\d+\)", desc):
                # Flow step: "1) 장바구니에 테스트 상품 담기"
                steps.append(desc)
            elif re.match(r"AC\d+", desc, re.IGNORECASE):
                # Verification: "AC1: 옵션변경 버튼 존재 확인"
                steps.append(f"  ✓ {desc}")
            else:
                steps.append(desc)
            continue

        # Numbered comment: # 1) ...
        if num_re.match(line):
            steps.append(line.lstrip("# ").strip())
            continue

        # Key actions → human-readable
        if line.startswith("NAVIGATE "):
            url = line.split(None, 1)[1]
            steps.append(f"  → 페이지 이동: {url}")
        elif line.startswith("ENSURE_LOGIN_"):
            target = line.split()[0].replace("ENSURE_LOGIN_", "").replace("_", " ")
            steps.append(f"  → 로그인: {target}")
        elif line.startswith("PICK_ORDER_FROM_POOL "):
            parts = line.split()
            steps.append(f"  → 사전조건: '{parts[1]}' 상태 주문 준비")
        elif line.startswith("CLICK_SNAPSHOT_TEXT "):
            text = line.split(None, 1)[1].strip('"').strip("'")
            steps.append(f"  → 클릭: '{text}'")
        elif line.startswith("CLICK "):
            target = line.split(None, 1)[1]
            steps.append(f"  → 클릭: {target}")
        elif line.startswith("FILL "):
            parts = line.split(None, 2)
            steps.append(f"  → 입력: {parts[1]}에 값 입력")
        elif line.startswith(("CHECK ", "CHECK_URL ", "CHECK_NOT_URL ")):
            steps.append(f"  → 확인: {line}")
        elif line.startswith("SUBMIT_"):
            action = line.split("_", 1)[1].split("_REQUEST")[0].replace("_", " ").lower()
            steps.append(f"  → 제출: {action} 요청")
        elif line.startswith("DUMP_STATE "):
            steps.append(f"  → 결과 캡처: {line.split()[1]}")
    return steps


def _find_scn_for_story(story: str, scn_files: list[Path]) -> list[Path]:
    """Try to find .scn files related to a user story keyword."""
    keywords = [w for w in story.split() if len(w) >= 2]
    matched = []
    for path in scn_files:
        content = path.read_text(encoding="utf-8")
        for kw in keywords[:3]:
            if kw in content:
                matched.append(path)
                break
    return matched[:3]


def _collect_preconditions(scn_paths: list[Path]) -> list[dict]:
    """Collect preconditions from matched .scn files."""
    try:
        from executor.execute_scenario import parse_metadata
    except ImportError:
        return []

    result = []
    seen = set()
    for path in scn_paths:
        meta = parse_metadata(path)
        if meta.preconditions:
            key = str(sorted(meta.preconditions.items()))
            if key not in seen:
                seen.add(key)
                result.append({
                    "file": str(path.relative_to(REPO_ROOT)),
                    "title": meta.title,
                    "preconditions": dict(meta.preconditions),
                })
    return result


def _extract_meta_horizontal(row: list[str]) -> dict[str, str]:
    """Parse horizontal key-value metadata: PRD, url, , JIRA, url, ..."""
    meta: dict[str, str] = {}
    keys = {"PRD", "FIGMA", "JIRA", "티켓", "디자인", "테스트브랜치", "테스트 환경", "테스트환경"}
    i = 0
    while i < len(row):
        cell = row[i].strip()
        if cell in keys:
            # Next non-empty cell is the value
            for j in range(i + 1, min(i + 3, len(row))):
                if row[j].strip():
                    meta[cell] = row[j].strip()
                    i = j + 1
                    break
            else:
                i += 1
        else:
            i += 1
    return meta


def parse_qa_csv(path: Path) -> dict:
    """Parse QA sheet CSV into structured story → AC hierarchy.

    Auto-detects CSV format by finding the header row containing 'User Story'.
    """
    with open(path, encoding="utf-8") as f:
        rows = list(csv.reader(f))

    # --- Step 1: Find header row (contains 'User Story') ---
    header_idx = -1
    header: list[str] = []
    for ri, row in enumerate(rows[:10]):
        cells = [c.strip().lower() for c in row]
        if any("user story" in c for c in cells):
            header_idx = ri
            header = [c.strip() for c in row]
            break

    if header_idx < 0:
        # Fallback: guess header at row 5
        header_idx = 5
        header = [c.strip() for c in rows[5]] if len(rows) > 5 else []

    # --- Step 2: Parse metadata from rows before header ---
    meta: dict[str, str] = {}
    for row in rows[:header_idx]:
        if len(row) < 2:
            continue
        # Try vertical format: key in col 0, value in col 1
        k, v = row[0].strip(), row[1].strip()
        if k and v and len(k) < 20:
            meta[k] = v
        # Try horizontal format: key, value, , key, value, ...
        h_meta = _extract_meta_horizontal(row)
        meta.update(h_meta)

    # Resolve ticket
    ticket_url = meta.get("JIRA", meta.get("티켓", ""))
    ticket_id = ""
    if ticket_url and "atlassian" in ticket_url:
        ticket_id = ticket_url.rstrip("/").rsplit("/", 1)[-1]

    # --- Step 3: Detect column indices from header ---
    def _find_col(names: list[str]) -> int:
        for i, h in enumerate(header):
            hl = h.lower()
            if any(n in hl for n in names):
                return i
        return -1

    col_story = _find_col(["user story"])
    col_ac = _find_col(["acceptance", "ac"])
    col_screen = _find_col(["처리시점", "화면"])
    col_type = _find_col(["상품타입", "대상"])

    # For 옵션변경 format: story=3, ac_num=4, ac_desc=5
    # For 수량환불 format: story=1, ac=10
    # Detect if AC column has sub-number or is single description
    ac_has_separate_desc = (
        col_ac >= 0
        and col_ac + 1 < len(header)
        and not header[col_ac + 1]  # empty header = continuation
    )

    # Scan available .scn files for automation linking
    scn_files = sorted((REPO_ROOT / "scenarios").rglob("*.scn"))

    # --- Step 4: Parse data rows ---
    stories: list[dict] = []
    current_story: dict | None = None
    current_screen = ""

    for row in rows[header_idx + 1:]:
        if len(row) <= max(col_story, col_ac, 0):
            continue

        # Screen / product type
        type_col = col_type if col_type >= 0 else (col_screen if col_screen >= 0 else -1)
        if type_col >= 0 and type_col < len(row) and row[type_col].strip():
            current_screen = row[type_col].strip().replace("\n", " ")

        # Story text
        story_text = row[col_story].strip().replace("\n", " ") if col_story >= 0 and col_story < len(row) else ""

        # AC parsing depends on format
        if col_ac >= 0 and col_ac < len(row):
            ac_raw = row[col_ac].strip()
        else:
            ac_raw = ""

        # Check if there's a separate AC number column (옵션변경 style)
        # vs single AC column with description (수량환불 style)
        ac_num = ""
        ac_desc = ""
        if col_ac >= 0:
            # 옵션변경 format: col_ac is number, col_ac+1 is description
            if col_ac + 1 < len(header) and header[col_ac].lower() in ("acceptance creteria", "acceptance criteria", "ac"):
                # Check if header[col_ac] looks like the number column
                if ac_raw and ac_raw.replace(".", "").isdigit():
                    ac_num = ac_raw
                    ac_desc = row[col_ac + 1].strip() if col_ac + 1 < len(row) else ""
                elif ac_raw:
                    ac_desc = ac_raw
                else:
                    # Could be sub-item in next column
                    ac_desc = row[col_ac + 1].strip() if col_ac + 1 < len(row) else ""
            else:
                ac_desc = ac_raw

        if not ac_desc:
            continue

        # New story
        if story_text and (current_story is None or story_text != current_story["story"]):
            current_story = {
                "story": story_text,
                "screen": current_screen,
                "acs": [],
            }
            stories.append(current_story)

        if current_story is None:
            current_story = {"story": "", "screen": current_screen, "acs": []}
            stories.append(current_story)

        # AC might contain multiple lines (수량환불 format: "- line1\n- line2")
        ac_lines = [l.strip().lstrip("- ") for l in ac_desc.split("\n") if l.strip()]
        if len(ac_lines) > 1:
            for i, line in enumerate(ac_lines, 1):
                current_story["acs"].append({"num": str(i), "desc": line})
        else:
            current_story["acs"].append({"num": ac_num, "desc": ac_desc})

    # Try to match .scn files to stories + collect preconditions
    all_matched_scns = []
    try:
        from executor.execute_scenario import parse_metadata
        _has_parser = True
    except ImportError:
        _has_parser = False

    for story in stories:
        matched = _find_scn_for_story(story["story"], scn_files)
        story["scn_files"] = [str(p.relative_to(REPO_ROOT)) for p in matched]
        # Build per-scenario detail: title, priority, manual steps
        scn_details = []
        for p in matched:
            detail: dict = {
                "file": str(p.relative_to(REPO_ROOT)),
                "filename": p.stem,
                "status": "ready",  # ready | pass | fail (updatable by runner)
            }
            if _has_parser:
                scn_meta = parse_metadata(p)
                detail["title"] = scn_meta.title
                detail["priority"] = getattr(scn_meta, "priority", "")
            else:
                detail["title"] = p.stem.replace("_", " ")
                detail["priority"] = ""
            detail["manual_steps"] = _extract_manual_steps(p)
            scn_details.append(detail)
        story["scn_details"] = scn_details
        all_matched_scns.extend(matched)

    preconditions = _collect_preconditions(all_matched_scns)

    return {
        "ticket_id": ticket_id,
        "ticket_url": ticket_url,
        "prd_url": meta.get("PRD", ""),
        "design_url": meta.get("FIGMA", meta.get("디자인", "")),
        "test_env_url": meta.get("테스트브랜치", meta.get("테스트 환경", meta.get("테스트환경", ""))),
        "task_title": ticket_id,
        "task_name": path.stem.rsplit(" - ", 1)[-1] if " - " in path.stem else path.stem,
        "stories": stories,
        "preconditions": preconditions,
    }


def generate_html(data: dict) -> str:
    """Generate HTML QA report with Story > AC > Automation structure."""
    stories = data["stories"]
    total_ac = sum(len(s["acs"]) for s in stories)
    total_scn = sum(len(s.get("scn_details", [])) for s in stories)

    ticket_link = _jira_link(data["ticket_id"]) if data["ticket_id"] else ""
    prd_link = f'<a href="{data["prd_url"]}" target="_blank">PRD</a>' if data["prd_url"] else ""
    env_link = f'<a href="{data["test_env_url"]}" target="_blank">테스트 환경</a>' if data["test_env_url"] else ""
    meta_links = " | ".join(x for x in [prd_link, env_link] if x)

    # Build preconditions section
    preconditions = data.get("preconditions") or []
    if preconditions:
        _LABELS = {
            "order_status": "주문 상태", "claim_type": "클레임 유형",
            "product_type": "상품 유형", "payment": "결제 방식", "special": "특수 조건",
        }
        all_keys = []
        for p in preconditions:
            for k in p["preconditions"]:
                if k not in all_keys:
                    all_keys.append(k)
        known = list(_LABELS.keys())
        all_keys.sort(key=lambda k: (known.index(k) if k in known else 99, k))

        precond_ths = "".join(f"<th>{_LABELS.get(k, k)}</th>" for k in all_keys)
        precond_rows = []
        for p in preconditions:
            cells = "".join(f"<td>{p['preconditions'].get(k, '')}</td>" for k in all_keys)
            fname = p["file"].rsplit("/", 1)[-1].replace(".scn", "")
            precond_rows.append(f"<tr><td class='ac-desc'>{p['title']}</td><td><code class='scn-link'>{fname}</code></td>{cells}</tr>")

        preconditions_section = f"""
  <div class="section-title">Required Test Preconditions</div>
  <div class="story-card">
    <table class="ac-table">
      <thead><tr><th>시나리오</th><th>파일</th>{precond_ths}</tr></thead>
      <tbody>{''.join(precond_rows)}</tbody>
    </table>
  </div>"""
    else:
        preconditions_section = ""

    # Build story sections
    colors = ["#60a5fa", "#a78bfa", "#34d399", "#fbbf24", "#f87171", "#f472b6", "#38bdf8"]
    story_blocks = []
    for si, story in enumerate(stories):
        acs = story["acs"]
        scn_files = story.get("scn_files", [])
        automated = len(scn_files)
        color = colors[si % len(colors)]
        # AC items as styled list
        ac_items = []
        for ac in acs:
            num_label = f'<span class="ac-chip">{ac["num"]}</span>' if ac["num"] else ""
            ac_items.append(
                f'<div class="ac-item">'
                f'  <div class="ac-main">{num_label}<span class="ac-text">{ac["desc"]}</span></div>'
                f'</div>'
            )

        # Per-scenario manual test guides
        scn_details = story.get("scn_details", [])
        guide_blocks = []

        # 1) .scn 파일 기반 가이드
        for sd in scn_details:
            manual_steps = sd.get("manual_steps", [])
            if not manual_steps:
                continue
            step_lines = "".join(f"<li>{s}</li>" for s in manual_steps)
            guide_blocks.append(
                f'<details class="manual-guide">'
                f'<summary class="manual-guide-toggle">'
                f'<code class="scn-link">{sd["filename"]}.scn</code> '
                f'<span class="guide-title">{sd["title"]}</span> '
                f'<span class="guide-count">{len(manual_steps)}단계</span>'
                f'</summary>'
                f'<ol class="step-list">{step_lines}</ol>'
                f'</details>'
            )

        scn_section = ""
        if guide_blocks:
            scn_section = (
                f'<div class="scn-guide-section">'
                f'<div class="scn-guide-label">수동 테스트 가이드</div>'
                f'{"".join(guide_blocks)}'
                f'</div>'
            )

        n_guides = sum(1 for sd in scn_details if sd.get("manual_steps"))
        auto_badge = f'<span class="badge-auto">{n_guides}개 시나리오</span>' if n_guides else '<span class="badge-manual">자동화 미구현</span>'

        story_blocks.append(f"""
  <details class="story-card" open>
    <summary class="story-header" style="border-left: 4px solid {color};">
      <div class="story-left">
        <span class="story-num">{si + 1}</span>
        <span class="story-title">{story["story"] or story["screen"]}</span>
      </div>
      <div class="story-right">
        {auto_badge}
        <span class="ac-count">{len(acs)} ACs</span>
      </div>
    </summary>
    <div class="story-body">
      {scn_section}
      <div class="ac-list">
        {''.join(ac_items)}
      </div>
    </div>
  </details>""")

    html = f"""\
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QA Report — {data["ticket_id"]} {data.get("task_title","")}</title>
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
    background: var(--bg); color: var(--text);
    padding: 24px; line-height: 1.6;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 8px; }}
  a {{ color: #60a5fa; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .subtitle {{ color: var(--text-dim); font-size: 0.875rem; margin-bottom: 24px; }}

  /* Summary */
  .summary {{ display: flex; gap: 16px; margin-bottom: 32px; flex-wrap: wrap; }}
  .card {{
    background: var(--surface); border-radius: 12px;
    padding: 20px; border: 1px solid var(--border); min-width: 150px;
  }}
  .card-label {{ color: var(--text-dim); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .card-value {{ font-size: 2rem; font-weight: 700; margin-top: 4px; color: var(--text); }}

  /* Story Cards */
  .section-title {{ font-size: 1.125rem; font-weight: 600; margin-bottom: 16px; margin-top: 32px; }}
  .story-card {{
    background: var(--surface); border-radius: 12px;
    border: 1px solid var(--border); margin-bottom: 16px; overflow: hidden;
  }}
  .story-header {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 20px; background: var(--surface2);
    cursor: pointer; list-style: none; user-select: none;
    border-radius: 12px 12px 0 0;
  }}
  .story-header::-webkit-details-marker {{ display: none; }}
  .story-left {{ display: flex; align-items: center; gap: 12px; }}
  .story-right {{ display: flex; align-items: center; gap: 8px; }}
  .story-num {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; border-radius: 50%;
    background: rgba(96,165,250,0.15); color: #60a5fa;
    font-size: 0.8rem; font-weight: 700; flex-shrink: 0;
  }}
  .story-title {{ font-weight: 600; font-size: 0.95rem; }}
  .ac-count {{
    display: inline-block; padding: 3px 10px; border-radius: 12px;
    font-size: 0.75rem; font-weight: 600;
    background: rgba(148,163,184,0.15); color: var(--text-dim);
  }}
  .issue-count {{
    display: inline-block; padding: 3px 10px; border-radius: 12px;
    font-size: 0.75rem; font-weight: 600;
    background: rgba(239,68,68,0.1); color: #f87171;
  }}
  .story-body {{ padding: 0; }}
  details[open] .story-header {{ border-radius: 12px 12px 0 0; }}
  details:not([open]) .story-header {{ border-radius: 12px; }}

  .scn-link {{
    font-family: monospace; font-size: 0.72rem;
    background: rgba(96,165,250,0.12); padding: 3px 8px;
    border-radius: 4px; color: #60a5fa;
  }}
  .scn-guide-section {{
    border-bottom: 1px solid var(--border);
    background: rgba(96,165,250,0.03);
  }}
  .scn-guide-label {{
    padding: 10px 20px 4px; font-size: 0.75rem; font-weight: 600;
    color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em;
  }}
  .manual-guide {{
    padding: 6px 20px; border-top: 1px solid rgba(71,85,105,0.3);
  }}
  .manual-guide:first-of-type {{ border-top: none; }}
  .manual-guide-toggle {{
    font-size: 0.82rem; cursor: pointer; padding: 6px 0;
    user-select: none; display: flex; align-items: center; gap: 8px;
  }}
  .manual-guide-toggle:hover {{ color: #60a5fa; }}
  .guide-title {{ color: var(--text); font-weight: 500; }}
  .guide-count {{
    font-size: 0.7rem; color: var(--text-dim);
    background: var(--surface2); padding: 2px 8px; border-radius: 10px;
  }}
  .step-list {{
    margin: 8px 0 8px 8px; padding: 0;
    font-size: 0.8rem; color: var(--text-dim); line-height: 1.9;
  }}
  .step-list li {{
    padding: 2px 0; list-style: none;
  }}
  .step-list li::before {{
    content: '▸ '; color: var(--text-dim); opacity: 0.5;
  }}

  /* AC List */
  .ac-list {{ padding: 0; }}
  .ac-item {{
    padding: 12px 20px;
    border-bottom: 1px solid var(--border);
    transition: background 0.15s;
  }}
  .ac-item:last-child {{ border-bottom: none; }}
  .ac-item:hover {{ background: var(--surface2); }}
  .ac-section-label {{
    padding: 10px 20px 4px; font-size: 0.75rem; font-weight: 600;
    color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em;
    border-top: 1px solid var(--border);
  }}
  .ac-check {{
    width: 16px; height: 16px; margin-top: 3px; flex-shrink: 0;
    accent-color: var(--pass); cursor: pointer;
  }}
  .ac-item {{ display: flex; align-items: flex-start; gap: 10px; }}
  .ac-main {{ display: flex; align-items: flex-start; gap: 10px; }}
  .ac-chip {{
    display: inline-flex; align-items: center; justify-content: center;
    min-width: 30px; height: 22px; border-radius: 4px;
    background: var(--surface2); color: var(--text-dim);
    font-size: 0.72rem; font-weight: 600; font-family: monospace;
    flex-shrink: 0;
  }}
  .ac-text {{ font-size: 0.875rem; line-height: 1.5; }}
  .ac-issues {{ margin-top: 6px; margin-left: 40px; }}
  .ac-desc {{ max-width: 600px; }}

  /* AC Table (for preconditions) */
  .ac-table {{ width: 100%; border-collapse: collapse; }}
  .ac-table th {{
    text-align: left; padding: 10px 20px;
    font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.05em; color: var(--text-dim);
  }}
  .ac-table td {{ padding: 10px 20px; border-top: 1px solid var(--border); font-size: 0.875rem; }}
  .ac-table tr:hover td {{ background: var(--surface2); }}

  /* Badges */
  .badge-auto {{
    display: inline-block; padding: 3px 10px; border-radius: 12px;
    font-size: 0.72rem; font-weight: 600;
    background: rgba(34,197,94,0.12); color: var(--pass);
  }}
  .badge-manual {{
    display: inline-block; padding: 3px 10px; border-radius: 12px;
    font-size: 0.72rem; font-weight: 600;
    background: rgba(148,163,184,0.12); color: var(--text-dim);
  }}
  .issue-chip {{
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 0.72rem; background: rgba(239,68,68,0.1);
    color: #f87171; margin-right: 4px;
  }}

  /* Footer */
  .footer {{
    text-align: center; color: var(--text-dim); font-size: 0.75rem;
    margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--border);
  }}
</style>
</head>
<body>
<div class="container">
  <h1>&#128203; QA Report — {ticket_link} {data.get("task_name","")}</h1>
  <div class="subtitle">{meta_links} | {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>

  <div class="summary">
    <div class="card">
      <div class="card-label">User Stories</div>
      <div class="card-value">{len(stories)}</div>
    </div>
    <div class="card">
      <div class="card-label">Total ACs</div>
      <div class="card-value">{total_ac}</div>
    </div>
    <div class="card">
      <div class="card-label">자동화 시나리오</div>
      <div class="card-value" style="color:var(--pass)">{total_scn}</div>
    </div>
  </div>

  {preconditions_section}

  <div class="section-title">User Story &amp; 수동 테스트 시나리오</div>
  {''.join(story_blocks)}

  <div class="footer">
    Generated by order-agent QA Report | {datetime.now().isoformat(timespec='seconds')}
  </div>
</div>
</body>
</html>
"""
    return html


def main() -> int:
    open_browser = "--open" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--open"]

    if not args:
        print("Usage: python3 -m tools.generate_report_from_csv <csv_path> [--open]")
        return 1

    csv_path = Path(args[0])
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return 1

    data = parse_qa_csv(csv_path)
    html = generate_html(data)

    output_name = f"qa_report_{data['ticket_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    output_path = OUTPUT_DIR / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    total_ac = sum(len(s["acs"]) for s in data["stories"])
    print(f"Generated {output_path} ({len(html)} bytes)")
    print(f"  Ticket: {data['ticket_id']}")
    print(f"  Stories: {len(data['stories'])}, ACs: {total_ac}")

    if open_browser:
        webbrowser.open(f"file://{output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
