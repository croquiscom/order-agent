---
name: validate-scenario
description: "Validates .scn scenario files for syntax, actions, and safety policies before execution. Use when: 시나리오 검증, 문법 확인, validate, 시나리오 체크."
argument-hint: "[scenario.scn]"
---

# 시나리오 파일 검증

.scn 시나리오 파일의 문법, 액션, 셀렉터를 실행 전에 사전 검증한다.

**When to Use:** 새 시나리오 작성 후, 기존 시나리오 수정 후, 전체 일괄 검증
**Not for:** 시나리오 실행 → `run-scenario` | 시나리오 생성 → `new-scenario`

---

## Execution Steps

1. $ARGUMENTS에 .scn 파일이 지정되면 해당 파일만, 없으면 전체를 검증:
   - `services/zigzag/scenarios/*.scn`
   - `services/naver/scenarios/*.scn`

2. 각 파일에 대해 아래를 검증:

   a) **파싱 검증**: shlex.split 기반 토큰 파싱 정상 여부
   b) **액션 검증**: ALLOWED_ACTIONS 포함 여부 (25개)
   c) **인자 수 검증**: 각 액션의 필수 인자 개수
   d) **안전 정책**: `CLICK confirm_payment` 차단 확인
   e) **드라이런**: `--dry-run` 모드로 CLI 변환까지 검증

3. 결과를 파일별로 요약:
   - 통과/실패 수
   - 실패 시 라인 번호와 오류 내용

---

## 예시

- `/validate-scenario` — 전체 시나리오 검증
- `/validate-scenario alpha_claim_exchange.scn` — 특정 파일 검증
- `/validate-scenario services/naver/scenarios/smoke_naver.scn` — 네이버 시나리오

---

**Related Skills:**
- [run-scenario](../run-scenario/SKILL.md) - 시나리오 실행
- [new-scenario](../new-scenario/SKILL.md) - 시나리오 생성
