# /validate-scenario - 시나리오 파일 검증

## 목적
.scn 시나리오 파일의 문법, 액션, 셀렉터를 실행 전에 사전 검증한다.
새 시나리오를 작성하거나 기존 시나리오를 수정한 후 문법 오류를 사전에 잡는다.

## 사용 시점
- 새 시나리오 파일 작성 후
- 기존 시나리오 수정 후
- 전체 시나리오 일괄 검증 시

## 실행 방법

1. $ARGUMENTS에 .scn 파일이 지정되면 해당 파일만, 없으면 전체를 검증한다:
   - `services/zigzag/scenarios/*.scn`
   - `services/naver/scenarios/*.scn`

2. 각 파일에 대해 아래를 검증한다:

   a) **파싱 검증**: shlex.split 기반 토큰 파싱이 정상인지
   b) **액션 검증**: ALLOWED_ACTIONS에 포함된 액션인지
      - 허용: NAVIGATE, CLICK, FILL, WAIT_FOR, CHECK, PRESS, CHECK_URL,
        CHECK_NOT_URL, WAIT_URL, DUMP_STATE, CHECK_NEW_ORDER_SHEET, EVAL,
        ENSURE_LOGIN_ALPHA, CLICK_SNAPSHOT_TEXT, SUBMIT_CANCEL_REQUEST,
        SUBMIT_RETURN_REQUEST, SUBMIT_EXCHANGE_REQUEST 등 25개
   c) **인자 수 검증**: 각 액션의 필수 인자 개수 확인
   d) **안전 정책**: CLICK confirm_payment 차단 여부
   e) **드라이런**: `--dry-run` 모드로 CLI 변환까지 검증

3. 결과를 파일별로 요약한다:
   - 통과/실패 수
   - 실패 시 라인 번호와 오류 내용

## 예시
- `/validate-scenario` — 전체 시나리오 검증
- `/validate-scenario alpha_claim_exchange.scn` — 특정 파일 검증
- `/validate-scenario services/naver/scenarios/smoke_naver.scn` — 네이버 시나리오 검증
