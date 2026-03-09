---
name: clean-logs
description: "Cleans up old log files and screenshots from the logs/ directory with configurable retention. Use when: 로그 정리, 로그 삭제, 디스크 정리, clean logs, 로그 청소."
argument-hint: "[3d | 7d | 24h | all]"
---

# 오래된 로그 정리

logs/ 디렉터리에 축적되는 로그 파일과 스크린샷을 정리한다.

**When to Use:** 디스크 공간 확보, 오래된 테스트 결과 정리, 새 테스트 세션 시작
**Not for:** 로그 분석 → `check-logs` | 실패 분석 → `analyze-failure`

---

## Execution Steps

1. $ARGUMENTS에서 보존 기간을 파싱 (기본: 3d = 3일):
   - 숫자+d: 일 단위 (예: 7d)
   - 숫자+h: 시간 단위 (예: 24h)
   - `all`: 전체 삭제 (.gitkeep 제외)

2. `logs/`에서 보존 기간 이전 파일 수집:
   - `*.log`, `*.png`, `*.txt`, `*.json`
   - `.gitkeep`는 항상 제외

3. 삭제 대상을 사용자에게 보여준다:
   - 파일 수, 총 용량
   - 가장 오래된/최근 파일 날짜

4. **반드시 사용자 확인을 받은 후** 삭제를 실행한다.

5. 정리 결과 보고:
   - 삭제된 파일 수 / 확보된 용량
   - 남은 파일 수

---

## 예시

- `/clean-logs` — 3일 이전 로그 정리
- `/clean-logs 7d` — 7일 이전 로그 정리
- `/clean-logs 12h` — 12시간 이전 로그 정리
- `/clean-logs all` — 전체 정리 (.gitkeep 제외)

---

**Related Skills:**
- [check-logs](../check-logs/SKILL.md) - 로그 분석
