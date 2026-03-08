# /run-scenario - 시나리오 실행

## 목적
커머스 주문 플로우 자동화 시나리오(.scn)를 빠르게 실행한다.
매번 `python3 services/zigzag/scripts/execute_scenario.py ...`를 타이핑하는 반복을 제거한다.
단일 시나리오는 물론, 여러 시나리오를 연결 실행할 수도 있다.

## 사용 시점
- 시나리오 파일을 실행할 때
- 여러 시나리오를 이어서 실행할 때 (주문 → 클레임 등)
- 드라이런으로 검증할 때
- 특정 옵션(--continue-on-error, --keep-browser-open 등)과 함께 실행할 때

## 실행 방법

사용자의 $ARGUMENTS를 파싱하여 아래 규칙으로 실행한다:

1. 인자가 없으면 기본 시나리오를 실행:
   ```
   python3 services/zigzag/scripts/execute_scenario.py
   ```

2. `.scn` 파일명이 하나 이상 포함되면 해당 시나리오를 순차 실행:
   ```
   python3 services/zigzag/scripts/execute_scenario.py <file1.scn> [file2.scn] [file3.scn]
   ```
   - 파일명만 주어졌으면 `services/zigzag/scenarios/` 에서 탐색

3. 키워드로 시나리오 그룹 지정 가능 (다중 실행):
   - `order+cancel`: 주문 생성 → 취소 클레임
   - `order+return`: 주문 생성 → 반품 클레임
   - `order+exchange`: 주문 생성 → 교환 클레임
   - `all-claims`: 주문 생성 → 취소/반품/교환 순차 실행
   - `all`: 전체 시나리오 실행

   키워드 매핑:
   - `order` → `alpha_direct_buy_order_normal.scn`
   - `cancel` → `alpha_claim_cancel.scn`
   - `return` → `alpha_claim_return.scn`
   - `exchange` → `alpha_claim_exchange.scn`

4. 주요 옵션:
   - `--dry-run`: 실제 브라우저 없이 파싱/검증만
   - `--continue-on-error`: 에러 발생해도 계속 진행
   - `--stop-on-scenario-fail`: 시나리오 하나 실패 시 나머지 중단 (다중 실행 시)
   - `--keep-browser-open`: 종료 후 브라우저 유지
   - `--keep-browser-alive`: 실행 중 세션 유지
   - `--no-retry-on-overlay`: 오버레이 재시도 비활성화
   - `--url-wait-timeout-ms <ms>`: WAIT_URL 타임아웃 설정

5. 실행 완료 후 종료 코드를 확인하고 결과를 요약한다.
   - 다중 실행 시 SUMMARY 출력에서 각 시나리오별 성공/실패와 전체 통과율을 보고한다.

## 예시
- `/run-scenario` — 기본 시나리오
- `/run-scenario alpha_claim_cancel.scn` — 취소 클레임 시나리오
- `/run-scenario --dry-run alpha_direct_buy_order_normal.scn` — 드라이런
- `/run-scenario --continue-on-error alpha_full_history_regression.scn` — 회귀 테스트
- `/run-scenario alpha_direct_buy_order_normal.scn alpha_claim_cancel.scn` — 주문 → 취소 연결
- `/run-scenario order+cancel` — 주문 → 취소 (키워드)
- `/run-scenario order+return --keep-browser-open` — 주문 → 반품, 브라우저 유지
- `/run-scenario --dry-run all-claims` — 전체 클레임 드라이런
