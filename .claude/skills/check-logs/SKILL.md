---
name: check-logs
description: "Analyzes recent scenario execution logs and screenshots for quick pass/fail summary. Use when: 로그 확인, 결과 확인, 실행 결과, check logs, 로그 보여줘."
argument-hint: "[date | log-file]"
---

# 최근 실행 결과 분석

시나리오 실행 후 logs/ 디렉터리의 로그와 스크린샷을 빠르게 분석한다.

**When to Use:** 실행 직후 결과 확인, 특정 시간대 결과 조회, FAILED 라인 추출
**Not for:** 실패 원인 심층 분석 → `analyze-failure` | 로그 정리 → `clean-logs`

---

## Execution Steps

1. `logs/`에서 가장 최근 `order-agent-exec_*.log` 파일을 찾는다.
   - $ARGUMENTS에 날짜/시간 힌트가 있으면 해당 시간대 로그 탐색
   - 파일명이 있으면 해당 파일 직접 분석

2. 로그에서 아래 패턴 추출:
   - `FAILED` — 실패한 액션과 라인 번호
   - `ERROR` — 에러 메시지
   - `OK` — 성공한 액션 수
   - 실행 시작/종료 시간, 총 소요 시간

3. 동일 타임스탬프 관련 파일 확인:
   - `failed_line_*.png` — 실패 시점 스크린샷
   - `diag_*.png` / `diag_*.txt` — 진단 캡처
   - `result.png` — 최종 화면

4. 결과 요약 제공:
   - 전체 커맨드 수 / 성공 / 실패
   - 실패 항목별 라인 번호, 액션, 에러 메시지
   - 관련 스크린샷 목록

---

## 예시

- `/check-logs` — 가장 최근 로그 분석
- `/check-logs 20260307` — 3/7 로그만 분석
- `/check-logs order-agent-exec_20260306_214920.log` — 특정 로그 분석

---

**Related Skills:**
- [analyze-failure](../analyze-failure/SKILL.md) - 실패 심층 분석
- [clean-logs](../clean-logs/SKILL.md) - 로그 정리
