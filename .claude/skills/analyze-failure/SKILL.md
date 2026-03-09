---
name: analyze-failure
description: "Analyzes scenario execution failures using logs, screenshots, and error context to identify root cause. Use when: 실패 분석, 왜 실패, 에러 원인, analyze failure, 시나리오 오류."
argument-hint: "[log-file | failed_line_N]"
---

# 시나리오 실패 분석

시나리오 실행 실패 시 로그, 스크린샷, 에러 메시지를 종합 분석하여 원인과 해결 방안을 제시한다.

**When to Use:** 시나리오 실패 원인 파악, 반복 실패 분석, 클레임 처리 실패 근본 원인 분석
**Not for:** 단순 로그 조회 → `check-logs` | 브라우저 연결 문제 → `browser-status`

---

## Execution Steps

1. **실패 로그 식별**
   - $ARGUMENTS에 로그 파일명이 있으면 해당 파일 분석
   - 없으면 `logs/order-agent-exec_*.log` 중 가장 최근 FAILED 포함 파일

2. **로그에서 실패 정보 추출**
   - FAILED 라인의 line_no, 액션, 에러 메시지
   - 에러 직전/직후 컨텍스트 (전후 5줄)
   - AgentBrowserError의 stderr 내용

3. **관련 스크린샷 수집**
   - `failed_line_{line_no}_*.png` — 실패 시점 화면
   - `diag_*.png` — 동일 타임스탬프 진단 캡처
   - 스크린샷을 Read 도구로 읽어 시각적으로 분석

4. **원본 시나리오 대조**
   - 로그에서 실행된 .scn 파일 경로 추출
   - 실패한 라인의 원본 커맨드 확인
   - 전후 커맨드 흐름 분석

5. **실패 패턴 분류**
   - `Element not found` — 셀렉터 변경 또는 페이지 미로딩
   - `blocked by another element` — 오버레이/모달 가림
   - `timeout expired` — 페이지 로딩 지연
   - `execution context was destroyed` — 페이지 전환 경합
   - `reason_option_not_found` — 클레임 사유 UI 변경
   - `CANCEL/RETURN/EXCHANGE_REQUEST_STUCK` — 제출 후 페이지 미전환
   - `upstream error` / `502` — 서버 에러

6. **분석 결과 보고**
   - 실패 원인 요약 + 해결 방안 제시
   - 필요 시 수정된 시나리오 라인 제안

---

## 예시

- `/analyze-failure` — 가장 최근 실패 분석
- `/analyze-failure order-agent-exec_20260306_214920.log` — 특정 로그 분석
- `/analyze-failure failed_line_18` — 18번 라인 실패만 분석

---

**Related Skills:**
- [check-logs](../check-logs/SKILL.md) - 로그 조회
- [run-scenario](../run-scenario/SKILL.md) - 시나리오 재실행
- [browser-status](../browser-status/SKILL.md) - 브라우저 상태 확인
