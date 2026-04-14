"""실행 로그를 Haiku로 분석하여 QA 리포트를 생성하는 스크립트.

사용법:
    # 특정 로그 파일들 분석
    python3 executor/generate_qa_report.py logs/order-agent-exec_20260413_*.log

    # 최근 N개 로그 자동 선택
    python3 executor/generate_qa_report.py --recent 5

    # 기간별 트렌드 분석
    python3 executor/generate_qa_report.py logs/order-agent-exec_202604*.log --trend

    # 출력 파일 지정
    python3 executor/generate_qa_report.py logs/*.log -o reports/qa_report.md
"""

from __future__ import annotations

import argparse
import glob
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------

_LOG_LINE_RE = re.compile(
    r"\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)\]\s+"
    r"(?P<level>\w+)\s+"
    r"(?P<msg>.*)"
)
_STEP_RE = re.compile(r"\[STEP (?P<cur>\d+)/(?P<total>\d+)\] line (?P<line>\d+): (?P<action>.+)")
_SCENARIO_RE = re.compile(r"Loading scenario: (?P<path>.+)")
_ERROR_RE = re.compile(r"(ERROR|FAIL|failed|Timeout|not found|not visible|blocked)", re.IGNORECASE)
_FINISH_RE = re.compile(r"Scenario execution finished with (?P<n>\d+) failure")
_DRYRUN_RE = re.compile(r"\[DRY-RUN\]")
_SELF_HEAL_RE = re.compile(r"Self-Heal|self.heal", re.IGNORECASE)
_TOTAL_CMD_RE = re.compile(r"Total commands: (?P<n>\d+)")


@dataclass
class StepInfo:
    step: int
    total: int
    line_no: int
    action: str
    error: str = ""


@dataclass
class LogSummary:
    path: str
    scenario: str = ""
    timestamp: str = ""
    is_dry_run: bool = False
    total_steps: int = 0
    steps: list[StepInfo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    self_heals: list[str] = field(default_factory=list)
    failure_count: int = 0
    raw_lines: int = 0


def parse_log(path: str) -> LogSummary:
    """단일 로그 파일을 파싱하여 LogSummary를 반환."""
    summary = LogSummary(path=path)
    lines: list[str] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return summary

    summary.raw_lines = len(lines)
    current_step: StepInfo | None = None
    max_step_total = 0

    for raw in lines:
        raw = raw.rstrip()
        m = _LOG_LINE_RE.match(raw)
        if not m:
            continue

        ts, level, msg = m.group("ts"), m.group("level"), m.group("msg")

        # 타임스탬프 (첫 줄)
        if not summary.timestamp:
            summary.timestamp = ts

        # 시나리오 경로 (INCLUDE 처리된 tmp 파일이 아닌 원본 우선)
        sm = _SCENARIO_RE.search(msg)
        if sm:
            path_val = sm.group("path")
            if not summary.scenario or (summary.scenario.startswith("/tmp") and not path_val.startswith("/tmp")):
                summary.scenario = path_val

        # Total commands
        tc = _TOTAL_CMD_RE.search(msg)
        if tc:
            summary.total_steps = int(tc.group("n"))

        # DRY-RUN 감지
        if _DRYRUN_RE.search(msg):
            summary.is_dry_run = True

        # 스텝 파싱
        step_m = _STEP_RE.search(msg)
        if step_m:
            current_step = StepInfo(
                step=int(step_m.group("cur")),
                total=int(step_m.group("total")),
                line_no=int(step_m.group("line")),
                action=step_m.group("action"),
            )
            summary.steps.append(current_step)
            step_total = int(step_m.group("total"))
            if step_total > max_step_total:
                max_step_total = step_total

        # 에러 수집
        if level == "ERROR" or (level == "WARNING" and _ERROR_RE.search(msg)):
            summary.errors.append(msg)
            if current_step and not current_step.error:
                current_step.error = msg

        # 실패 카운트
        fm = _FINISH_RE.search(msg)
        if fm:
            summary.failure_count = int(fm.group("n"))

        # Self-Heal
        if _SELF_HEAL_RE.search(msg):
            summary.self_heals.append(msg)

    # INCLUDE 확장으로 실제 스텝이 Total commands보다 많을 수 있음
    if max_step_total > summary.total_steps:
        summary.total_steps = max_step_total

    return summary


def parse_logs(paths: list[str]) -> list[LogSummary]:
    """여러 로그 파일을 파싱."""
    return [parse_log(p) for p in sorted(paths)]


# ---------------------------------------------------------------------------
# Structured pre-summary (LLM에 보낼 압축 텍스트)
# ---------------------------------------------------------------------------

def _scenario_name(path: str) -> str:
    """시나리오 경로에서 파일명만 추출."""
    return Path(path).name if path else "(unknown)"


def build_structured_input(summaries: list[LogSummary], trend: bool = False) -> str:
    """파싱 결과를 LLM이 분석하기 좋은 구조화된 텍스트로 변환."""
    parts: list[str] = []

    total_files = len(summaries)
    total_errors = sum(s.failure_count for s in summaries)
    passed = sum(1 for s in summaries if s.failure_count == 0 and not s.is_dry_run)
    failed = sum(1 for s in summaries if s.failure_count > 0)
    dry_run = sum(1 for s in summaries if s.is_dry_run)

    parts.append(f"## 실행 개요")
    parts.append(f"- 분석 대상: {total_files}개 로그")
    parts.append(f"- 통과: {passed}, 실패: {failed}, 드라이런: {dry_run}")
    parts.append("")

    for s in summaries:
        name = _scenario_name(s.scenario)
        status = "DRY-RUN" if s.is_dry_run else ("FAIL" if s.failure_count > 0 else "PASS")
        parts.append(f"### [{status}] {name}")
        parts.append(f"- 로그: {Path(s.path).name}")
        parts.append(f"- 시간: {s.timestamp}")
        parts.append(f"- 스텝: {len(s.steps)}/{s.total_steps}")

        if s.errors:
            parts.append(f"- 에러 ({len(s.errors)}건):")
            for e in s.errors[:10]:  # 최대 10개
                parts.append(f"  - {e[:200]}")

        failed_steps = [st for st in s.steps if st.error]
        if failed_steps:
            parts.append("- 실패 스텝:")
            for st in failed_steps:
                parts.append(f"  - L{st.line_no} STEP {st.step}/{st.total}: {st.action[:80]}")
                parts.append(f"    에러: {st.error[:150]}")

        if s.self_heals:
            parts.append(f"- Self-Heal ({len(s.self_heals)}건):")
            for sh in s.self_heals[:5]:
                parts.append(f"  - {sh[:150]}")

        parts.append("")

    # 트렌드 모드: 셀렉터/액션별 실패 집계
    if trend and len(summaries) > 1:
        selector_fails: dict[str, int] = {}
        action_fails: dict[str, int] = {}
        for s in summaries:
            for st in s.steps:
                if st.error:
                    action_key = st.action.split()[0] if st.action else "UNKNOWN"
                    action_fails[action_key] = action_fails.get(action_key, 0) + 1
                    # 셀렉터 추출 (첫 번째 인자)
                    action_parts = st.action.split(maxsplit=1)
                    if len(action_parts) > 1:
                        selector = action_parts[1][:60]
                        selector_fails[selector] = selector_fails.get(selector, 0) + 1

        if action_fails:
            parts.append("## 실패 트렌드 (액션별)")
            for act, cnt in sorted(action_fails.items(), key=lambda x: -x[1]):
                parts.append(f"- {act}: {cnt}회 실패")
            parts.append("")

        if selector_fails:
            parts.append("## 실패 트렌드 (셀렉터별)")
            for sel, cnt in sorted(selector_fails.items(), key=lambda x: -x[1])[:15]:
                parts.append(f"- `{sel}`: {cnt}회 실패")
            parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Haiku 분석
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
당신은 order-agent QA 분석 전문가입니다.
order-agent는 .scn 시나리오 파일 기반 브라우저 자동화 테스트 도구이며,
CDP(Chrome DevTools Protocol)로 웹 브라우저를 제어합니다.

주어진 실행 로그 분석 결과를 기반으로 QA 리포트를 생성합니다.

리포트 형식 (마크다운):
1. **실행 요약**: 전체 통과/실패 카운트, 실행 일시
2. **실패 분석**: 각 실패 시나리오별 원인 추정 (셀렉터 변경, 타이밍, 네트워크 등)
3. **셀렉터 실패 패턴**: 반복 실패하는 셀렉터와 대안 제안
4. **권장 조치**: 우선순위별 수정 권장 사항 (체크리스트)

트렌드 데이터가 포함된 경우:
5. **트렌드 분석**: 반복 실패 패턴, 안정성 추이

규칙:
- 드라이런 결과는 별도 섹션으로 분리
- 에러 코드가 있으면 그대로 표기 (예: CLAIM_NOT_AVAILABLE, EXCHANGE_POLICY_BLOCKED)
- 불확실한 추정은 "추정:" 접두사 사용
- 한국어로 작성
"""


def analyze_with_cli(structured_input: str, trend: bool = False) -> str:
    """claude CLI를 통해 QA 리포트 생성 (API 키 불필요)."""
    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise RuntimeError("claude CLI가 PATH에 없습니다")

    user_prompt = "다음 시나리오 실행 로그 분석 결과를 기반으로 QA 리포트를 생성해주세요."
    if trend:
        user_prompt += "\n트렌드 데이터가 포함되어 있으니 반복 실패 패턴도 분석해주세요."
    user_prompt += f"\n\n{structured_input}"

    full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"

    result = subprocess.run(
        [claude_bin, "-p", "--model", "haiku", full_prompt],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI 실패 (exit={result.returncode}): {result.stderr[:200]}")
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Fallback: LLM 없이 로컬 리포트 생성
# ---------------------------------------------------------------------------

def build_local_report(summaries: list[LogSummary], trend: bool = False) -> str:
    """Anthropic API 없이 로컬에서 구조화된 리포트 생성."""
    parts: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    passed = [s for s in summaries if s.failure_count == 0 and not s.is_dry_run]
    failed = [s for s in summaries if s.failure_count > 0]
    dry_runs = [s for s in summaries if s.is_dry_run]

    parts.append(f"# QA 리포트 ({now})")
    parts.append("")
    parts.append("## 실행 요약")
    parts.append(f"- 전체: {len(summaries)} 시나리오")
    parts.append(f"- 통과: {len(passed)} | 실패: {len(failed)} | 드라이런: {len(dry_runs)}")
    parts.append("")

    if failed:
        parts.append("## 실패 분석")
        for s in failed:
            name = _scenario_name(s.scenario)
            parts.append(f"### {name}")
            parts.append(f"- 실패: {s.failure_count}건")
            for st in s.steps:
                if st.error:
                    parts.append(f"- L{st.line_no} `{st.action[:60]}` -> {st.error[:120]}")
            parts.append("")

    if dry_runs:
        parts.append("## 드라이런")
        for s in dry_runs:
            name = _scenario_name(s.scenario)
            parts.append(f"- {name}: {s.total_steps} 스텝 검증 완료")
        parts.append("")

    if passed:
        parts.append("## 통과 시나리오")
        for s in passed:
            name = _scenario_name(s.scenario)
            parts.append(f"- {name}: {s.total_steps} 스텝")
        parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def find_recent_logs(n: int) -> list[str]:
    """logs/ 디렉토리에서 최근 N개 실행 로그를 찾음."""
    log_dir = REPO_ROOT / "logs"
    pattern = str(log_dir / "order-agent-exec_*.log")
    files = sorted(glob.glob(pattern), reverse=True)
    return files[:n]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="실행 로그를 분석하여 QA 리포트 생성",
    )
    parser.add_argument(
        "logs",
        nargs="*",
        help="분석할 로그 파일 경로 (glob 패턴 지원)",
    )
    parser.add_argument(
        "--recent",
        type=int,
        default=0,
        help="최근 N개 로그를 자동 선택",
    )
    parser.add_argument(
        "--trend",
        action="store_true",
        help="기간별 실패 트렌드 분석 포함",
    )
    parser.add_argument(
        "-o", "--output",
        help="리포트 출력 파일 경로 (미지정 시 stdout)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="LLM 없이 로컬 구조화 리포트만 생성",
    )
    parser.add_argument(
        "--structured-only",
        action="store_true",
        help="LLM에 보낼 구조화 입력만 출력 (디버그용)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 로그 파일 수집
    log_files: list[str] = []
    if args.recent > 0:
        log_files = find_recent_logs(args.recent)
    elif args.logs:
        for pattern in args.logs:
            expanded = glob.glob(pattern)
            log_files.extend(expanded if expanded else [pattern])
    else:
        log_files = find_recent_logs(5)

    if not log_files:
        print("[ERROR] 분석할 로그 파일이 없습니다.", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] {len(log_files)}개 로그 파일 분석 중...", file=sys.stderr)

    # 파싱
    summaries = parse_logs(log_files)
    structured = build_structured_input(summaries, trend=args.trend)

    if args.structured_only:
        print(structured)
        return

    # 리포트 생성: --local 또는 기본 (CLI → 로컬 fallback)
    if args.local:
        report = build_local_report(summaries, trend=args.trend)
    else:
        try:
            print("[INFO] claude CLI로 분석 중...", file=sys.stderr)
            report = analyze_with_cli(structured, trend=args.trend)
        except RuntimeError as e:
            print(f"[WARN] CLI 실패 ({e}), 로컬 리포트로 대체합니다.", file=sys.stderr)
            report = build_local_report(summaries, trend=args.trend)

    # 출력
    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(f"[INFO] 리포트 저장: {out_path}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
