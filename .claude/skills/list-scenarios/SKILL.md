---
name: list-scenarios
description: "Lists all available .scn test scenarios with Korean descriptions grouped by category. Use when: 시나리오 목록, 어떤 시나리오, 테스트 목록, list scenarios, 몇번."
---

# 시나리오 목록 조회

사용 가능한 테스트 시나리오를 한글 설명과 함께 번호 목록으로 보여준다.

**When to Use:** 어떤 시나리오가 있는지 확인, 번호로 시나리오 선택 실행
**Not for:** 시나리오 직접 실행 → `run-scenario` | 시나리오 생성 → `new-scenario`

---

## Execution Steps

1. `services/*/scenarios/*.scn` 파일을 모두 탐색한다.

2. 각 파일의 첫 번째 `#` 주석 줄에서 한글 설명을 추출한다.

3. 아래 카테고리별로 그룹핑하여 번호 매긴 목록을 출력한다:
   - **주문 생성 — 스토어배송**: `*_normal.scn`
   - **주문 생성 — 직진배송**: `*_zigzin.scn`
   - **장바구니 기타**: `*_cart_multi_*.scn`
   - **클레임 (성공)**: `*_claim_{cancel,return,exchange}*.scn` (policy_blocked 제외)
   - **클레임 (실패/정책 차단)**: `*_policy_blocked.scn`
   - **결제/포인트 예외**: `*_payment_*`, `*_insufficient_*`
   - **기타**: 위 카테고리에 속하지 않는 zigzag 시나리오
   - **네이버**: `services/naver/scenarios/*.scn`

4. 목록에 없는 새 `.scn` 파일이 발견되면 해당 카테고리에 자동 추가한다.

5. 목록 출력 후 안내:
   ```
   번호를 입력하면 해당 시나리오를 실행합니다.
   여러 개를 선택하려면 쉼표로 구분하세요 (예: 1,6)
   ```

6. 사용자가 번호를 입력하면:
   - 해당 번호의 `.scn` 파일 경로를 조합
   - `/run-scenario <파일경로>` 스킬을 호출하여 실행
   - 여러 번호인 경우 순차 실행

---

## 예시

- `/list-scenarios` — 전체 목록 표시 후 선택 대기

---

**Related Skills:**
- [run-scenario](../run-scenario/SKILL.md) - 시나리오 실행
- [new-scenario](../new-scenario/SKILL.md) - 시나리오 생성
