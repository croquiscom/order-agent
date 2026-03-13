# Claude Project Guide: order-agent

## 0) 작업 배경 및 목표
### 작업 배경
- 내부망 환경에서 커머스 웹서비스의 주문 플로우 자동화 테스트가 필요함.
- 지그재그(Zigzag)는 동적 UI와 다양한 상품/결제 옵션을 갖춘 플랫폼으로 수동 테스트가 반복적이고 시간 소모적임.
- 내부망 보안 정책상 외부 API 호출 제한, 실제 결제 발생 방지 등 제약 조건이 존재함.
- 따라서 브라우저 기반 자동화 + AI 시나리오 생성 방식으로 효율적 테스트 체계를 구축해야 함.

### 프로젝트 목표
- 내부망 환경에서 커머스 웹사이트 주문 흐름 자동화로 테스트 반복성 확보.
- 사람이 작성한 시나리오 기반으로 테스트 케이스를 신속하게 실행 가능하도록 설계.
- Claude 연동을 통해 시나리오 자동 생성/수정 기능 제공.
- `agent-browser` 기반 브라우저 제어로 UI 동적 변화 대응.
- 테스트 안전성 확보: 테스트 계정 사용, 실제 결제 금지.
- 테스트 대상 기본 도메인: `https://alpha.zigzag.kr/`.

## 1) 프로젝트 목적
- 내부망 환경에서 커머스 웹 주문/검색 플로우를 시나리오(`.scn`) 기반으로 자동화하는 Python 프로젝트.
- 핵심은 `executor/execute_scenario.py`가 시나리오를 파싱해 `agent-browser` CLI를 순차 호출하는 구조.
- 브라우저 컨트롤은 `agent-browser`만 사용하고 `openclaw`는 사용하지 않음.

## 2) 루트 구조
- `core/`
  - `runner.py`: `agent-browser` subprocess 래퍼 (`agent_browser()`), 실패 시 `AgentBrowserError` 발생.
  - `logger.py`: `logs/` 파일 + 콘솔 핸들러 로깅.
  - `agent_browser.py`: CDP 직접 제어 구현(웹소켓 기반). `python -m core.agent_browser ...`로 단독 실행 가능.
  - `otp_reader.py`: CDP로 Authenticator 확장프로그램에서 OTP 코드 읽기.
- `executor/`
  - `execute_scenario.py`: 범용 시나리오 실행 엔트리포인트.
  - `generate_scenario_claude.py`: Anthropic API로 시나리오 생성.
  - `run_with_playwright.py`: 이름과 달리 Playwright가 아니라 `core.agent_browser` 사용.
- `scenarios/`
  - `zigzag/*.scn`: Zigzag 주문/클레임 시나리오.
  - `naver/*.scn`: 네이버 검증용 시나리오.
  - `aws/*.scn`: AWS SSO 로그인 등 인프라 시나리오.
- `scripts/run_scenario_chrome.sh`: Chrome GUI 환경변수 설정 후 `execute_scenario.py` 실행.
- `tests/`: 파서/러너/로거 단위 테스트.
- `logs/`: 실행 로그/스크린샷 산출물.
- `requirements.txt`: `anthropic>=0.40.0`

## 3) 실행 흐름
1. `executor/execute_scenario.py`가 `.scn`을 읽어 `ScenarioCommand` 리스트 생성.
2. `validate_command()`로 액션/인자/결제 안전정책 검증.
3. `to_agent_browser_args()`로 `agent-browser` CLI 인자 변환.
4. `core.runner.agent_browser()`로 subprocess 실행.
5. 로그는 `logs/order-agent-exec_YYYYMMDD_HHMMSS.log`로 기록.

## 4) 시나리오 DSL (현재 코드 기준)
허용 액션 (`executor/execute_scenario.py`의 `ALLOWED_ACTIONS`):

기본 브라우저 제어:
- `NAVIGATE <url>` — URL 이동
- `CLICK <selector_or_id>` — 요소 클릭
- `FILL <selector_or_id> <value...>` — 입력 필드에 값 입력 (CDP 직접 전송)
- `WAIT_FOR <selector_or_id|milliseconds>` — 요소 출현 또는 밀리초 대기
- `CHECK <selector_or_id>` — 요소 존재 확인
- `PRESS <key>` — 키보드 키 입력

URL 검증:
- `CHECK_URL <substring>` — 현재 URL에 substring 포함 확인
- `CHECK_NOT_URL <substring>` — 현재 URL에 substring 미포함 확인
- `WAIT_URL <substring>` — URL에 substring이 나타날 때까지 대기 (타임아웃: `--url-wait-timeout-ms`)

주문/결제 검증:
- `CHECK_NEW_ORDER_SHEET` — 새 주문서 ID 생성 확인 (인자 없음)
- `SAVE_ORDER_DETAIL_ID` — 현재 주문상세 ID 저장 (인자 없음)
- `CHECK_ORDER_DETAIL_ID_CHANGED` — 저장된 주문상세 ID가 변경되었는지 확인 (인자 없음)
- `SAVE_ORDER_NUMBER` — 현재 주문번호 저장 (인자 없음)
- `CHECK_ORDER_NUMBER_CHANGED` — 저장된 주문번호가 변경되었는지 확인 (인자 없음)
- `CHECK_PAYMENT_RESULT` — 결제 결과 검증 (인자 없음)

주문 목록/장바구니 조작:
- `CLICK_ORDER_DETAIL_BY_STATUS <status>` — 주문 상태별 주문상세 클릭
- `CLICK_ORDER_DETAIL_WITH_ACTION <action>` — 특정 액션이 있는 주문상세 클릭
- `APPLY_ORDER_STATUS_FILTER <filter>` — 주문 상태 필터 적용
- `SELECT_CART_ITEM_BY_TEXT <text>` — 텍스트로 장바구니 아이템 선택

클레임 요청 제출:
- `SUBMIT_CANCEL_REQUEST <reason>` — 취소 클레임 요청 제출
- `SUBMIT_RETURN_REQUEST <reason>` — 반품 클레임 요청 제출
- `SUBMIT_EXCHANGE_REQUEST <reason>` — 교환 클레임 요청 제출

스냅샷 기반 조작:
- `CLICK_SNAPSHOT_TEXT <text>` — 접근성 스냅샷에서 텍스트 매칭으로 클릭
- `CLICK_PREV_CHECKBOX_FOR_SNAPSHOT_TEXT <text>` — 스냅샷 텍스트 앞의 체크박스 클릭

인증/유틸리티:
- `ENSURE_LOGIN_ALPHA` — alpha 환경 자동 로그인 (`ALPHA_USERNAME`/`ALPHA_PASSWORD` 환경변수 필요)
- `READ_OTP <account_name> [var_name]` — Authenticator 확장프로그램에서 OTP 읽어 `{{var_name}}` 변수에 저장 (기본 var: `otp`)
- `EVAL <expression>` — JavaScript 표현식 실행
- `DUMP_STATE <tag>` — 현재 페이지 상태 덤프

디버깅/테스트 제어:
- `PRINT_ACTIVE_MODAL` — 현재 활성 모달 상태 출력 (인자 없음)
- `EXPECT_FAIL [error_pattern]` — 다음 액션이 실패할 것으로 예상 표시 (선택적 에러 코드 패턴)

파싱 규칙:
- 빈 줄, `#` 주석 줄 무시.
- `shlex.split` 기반이라 따옴표 문자열 지원.

셀렉터 정규화:
- `@ # . [ / xpath= text= role=` 접두사가 없으면 legacy 호환으로 `@`를 자동 부여.

## 5) 안전 정책
- `CLICK confirm_payment`는 기본 차단.
- 정말 필요한 경우에만 `ALLOW_REAL_PAYMENT=1` 환경변수로 해제.
- 시나리오 생성기(`executor/generate_scenario_claude.py`)도 동일 정책으로 차단 검증.

## 6) 주요 커맨드
- 초기 설정 (Claude Code 스킬):
  - `/setup` — Python, agent-browser, .env, Chrome 등 환경 한번에 검증/설정
  - 수동 실행 대응: `./scripts/setup_env.sh`, `./scripts/doctor.sh`, `python3 executor/doctor.py --json`, `make doctor`
- 기본 실행:
  - `python3 executor/execute_scenario.py`
- 특정 시나리오:
  - `python3 executor/execute_scenario.py <path/to/file.scn>`
- 드라이런:
  - `python3 executor/execute_scenario.py --dry-run`
- 에러 계속 진행:
  - `python3 executor/execute_scenario.py --continue-on-error`
- 오버레이 재시도 비활성화:
  - `python3 executor/execute_scenario.py --no-retry-on-overlay`
- CLICK fallback 비활성화:
  - `python3 executor/execute_scenario.py --disable-click-fallback`
- 빠른 실패 모드 (timeout=12s + click fallback 비활성화):
  - `python3 executor/execute_scenario.py --fast-mode`
- WAIT_URL 타임아웃 설정:
  - `python3 executor/execute_scenario.py --url-wait-timeout-ms 30000 <scenario.scn>`
- 멀티 시나리오 실행 시 실패 즉시 중단:
  - `python3 executor/execute_scenario.py --stop-on-scenario-fail *.scn`
- 기본 URL 오버라이드:
  - `python3 executor/execute_scenario.py --base-url https://staging.zigzag.kr <scenario.scn>`
- keep-alive ping 간격 설정:
  - `python3 executor/execute_scenario.py --keep-browser-alive --keep-alive-interval-sec 15 <scenario.scn>`
- Claude 시나리오 생성:
  - `python3 executor/generate_scenario_claude.py "<prompt>"`
- AWS SSO 로그인:
  - `python3 executor/execute_scenario.py scenarios/aws/sso_login.scn --var username=<email> --var password=<pw>`

## 7) 환경/의존성
- Python 3.12+
- 실행 시 `agent-browser` CLI가 PATH에 있어야 함.
- `pip install -r requirements.txt` — `anthropic>=0.40.0`, `python-dotenv`, `websocket-client`
- `.env` 파일 지원: `python-dotenv`로 자동 로드 (미설치 시 환경변수 직접 설정)
- 시나리오 생성 시 `ANTHROPIC_API_KEY` 필요.
- `ENSURE_LOGIN_ALPHA` 액션 사용 시 `ALPHA_USERNAME`/`ALPHA_PASSWORD` 환경변수 필요.
- 테스트 실행: `python3 -m pytest -q`

## 8) CDP 직접 입력 패턴 (agent-browser 우회)
### 문제
- `agent-browser fill`은 특수문자(`!`, `@`, `#` 등)를 셸 이스케이프하는 버그가 있음.
- 예: `Lyjguy123!@#` → `Lyjguy123\!@#`로 변환되어 React SPA 폼에 잘못된 값 입력.

### 해결: `_cdp_direct_fill()` (executor/execute_scenario.py)
- CDP `Input.dispatchKeyEvent`로 한 글자씩 keyDown/keyUp 전송.
- React 등 SPA 프레임워크의 가상 DOM 이벤트 시스템과 호환됨.
- 모든 `FILL` 액션이 이 함수를 통해 실행됨 (agent-browser CLI 우회).

### 시도했으나 실패한 접근법
- `nativeInputValueSetter` + `dispatchEvent`: React state 미반영.
- `Input.insertText`: React 폼에서 state 업데이트 안 됨.
- 위 방법들은 일반 HTML 폼에서는 동작하지만 React/SPA에서는 사용 불가.

### 확장프로그램 OTP 읽기 (core/otp_reader.py)
- CDP `Target.createTarget`으로 확장프로그램 팝업을 새 탭으로 열기.
- `Runtime.evaluate`로 `document.body.innerText` 읽어 계정명 매칭 후 6자리 OTP 추출.
- Authenticator 확장프로그램 ID: `bhghoamapcdpbohphigoooaddinpkbai`, 팝업: `view/popup.html`.
- 시나리오 DSL: `READ_OTP "계정명" 변수명` → `{{변수명}}`으로 후속 FILL에 사용.

## 9) 셀렉터 작성 가이드
### 우선순위 (안정성 높은 순)
1. `role=textbox`, `role=button` — Playwright ARIA role 셀렉터, UI 변경에 강함.
2. `button[type=submit]`, `input[name=...]` — CSS 속성 셀렉터, ID보다 안정적.
3. `#fixed-id` — 고정 ID가 있는 경우.
4. `text=...` — 최후 수단. 부분 일치로 의도치 않은 요소 매칭 위험.

### 주의사항
- 동적 ID(`#awsui-input-0` 등)는 페이지 렌더링마다 변할 수 있어 사용 금지.
- `text=로그인`처럼 짧은 텍스트는 헤딩/링크 등 여러 요소에 매칭될 수 있음.
- `normalize_selector()`는 `[`, `>` 포함 시 CSS 셀렉터로 인식하여 `@` 접두사를 붙이지 않음.

## 10) 시나리오 작업 시 필수 참조 문서
- **시나리오 작성 종합 가이드**: `/scenario-guide` 스킬 (`.claude/skills/scenario-guide/SKILL.md`) — 구조 패턴, 셀렉터 전략, 안전 정책, 동기화 체크리스트 포함
- **`/new-scenario` 실행 시 자동으로 가이드를 로딩**하므로 별도 참조 없이 시나리오 생성 가능
- **시나리오 수정/생성/디버깅 전에 반드시 아래 문서를 먼저 읽을 것:**
  - `docs/input_interaction_patterns.md`: 클레임(교환/반품/취소) 플로우의 입력 UI 패턴, 셀렉터 전략, 결제 패턴, URL 분기 처리, 트러블슈팅
  - `docs/exchange_stabilization_plan.md`: 교환 시나리오 안정화 우선순위 및 완료 조건
- **기준 시나리오 (레퍼런스):**
  - 교환: `alpha_claim_exchange.scn` — 파생 시나리오(`_by_order`, `_policy_blocked`, `_input_option`)는 이 패턴과 동기화 유지
  - 반품: `alpha_claim_return.scn`
  - 취소: `alpha_claim_cancel.scn`
- 파생 시나리오에 EVAL을 직접 작성하지 말고, 기준 시나리오의 검증된 EVAL을 복사하여 사용할 것
- 셀렉터 범위 변경 시(예: `querySelectorAll` 대상 태그 축소) 반드시 실제 DOM 구조(`div.btn` 등)와 대조 확인

## 11) 변경 시 유의사항
- 시나리오 액션을 추가/변경하면 아래를 함께 맞출 것:
  - `executor/execute_scenario.py`: `ALLOWED_ACTIONS`, 검증, CLI 변환
  - `executor/generate_scenario_claude.py`: 액션 검증/시스템 프롬프트
  - `scenarios/*/*.scn`: 샘플/스모크 시나리오
  - `tests/*`: 파싱/변환/실행 테스트
- 자동화 결과 판단은 로그(`logs/*.log`)와 스크린샷(`logs/*.png`)을 함께 확인.
- 클릭이 오버레이에 가릴 수 있어 실행기는 기본적으로 `ESC` 후 1회 재시도함.
- `CLICK text=...`가 실패하면 실행기는 `find text <value> click` fallback을 1회 수행함.

## 12) 실제 브라우저 환경 테스트 가이드
브라우저 기반:
- 본 프로젝트의 실제 브라우저 테스트는 Chrome/Chromium + CDP(DevTools Protocol) 기반.
- macOS 기본 경로: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- 테스트 대상 기본 도메인: `https://alpha.zigzag.kr/`
- 브라우저 활성화 정책: auto-connect(CDP) 우선, 실패 시 실행경로 자동 탐색 후 기동

사전 준비:
- Chrome(또는 Chromium) 설치
- `agent-browser` CLI 실행 가능 상태(PATH 등록)
- 테스트 대상 시나리오 파일 준비 (`scenarios/*/*.scn`)
- 필요 시 환경변수로 활성화 제어:
  - 브라우저 연결:
    - `AGENT_BROWSER_AUTO_CONNECT` (기본 `1`) — 기존 브라우저 auto-attach
    - `ORDER_AGENT_BROWSER_AUTO_CONNECT` — 위 변수의 fallback (미설정 시 기본 `1`)
    - `AGENT_BROWSER_EXECUTABLE_PATH` — 브라우저 실행 경로 수동 지정
    - `ORDER_AGENT_DISABLE_BROWSER_PATH_RESOLVE` (`1`이면 자동 경로탐색 비활성화)
    - `ORDER_AGENT_CDP_PORT` (기본 `9222`)
    - `ORDER_AGENT_BROWSER_ATTACH_ONLY` (`1`이면 attach 전용, 브라우저 기동 안 함)
  - 브라우저 기동 옵션:
    - `ORDER_AGENT_BROWSER_PROFILE_DIR` — 전용 user-data-dir
    - `ORDER_AGENT_BROWSER_HEADLESS` — 헤드리스 모드
    - `ORDER_AGENT_BROWSER_NO_SANDBOX` — 샌드박스 비활성화
    - `ORDER_AGENT_BROWSER_EXTRA_ARGS` — 추가 Chrome 실행 인자
    - `ORDER_AGENT_BROWSER_DISABLE_EXTENSIONS` — 확장프로그램 없이 기동
    - `ORDER_AGENT_DISABLE_BROWSER_BOOTSTRAP` — 브라우저 자동 기동/관리 비활성화
  - CDP 제어:
    - `ORDER_AGENT_DISABLE_CDP_INJECTION` — `--cdp` 플래그 자동 주입 비활성화
    - `ORDER_AGENT_DISABLE_CDP_TAB_SANITIZE` — 시작 시 CDP 탭 정리 비활성화
    - `ORDER_AGENT_AGENT_BROWSER_TIMEOUT_SEC` — agent-browser subprocess 타임아웃 (기본: 20초)
  - 시나리오 실행:
    - `ALPHA_USERNAME` / `ALPHA_PASSWORD` — `ENSURE_LOGIN_ALPHA` 액션에 필요
    - `ORDER_AGENT_REASON_TEXT` — 클레임 사유 텍스트 사전 지정
    - `ORDER_AGENT_REASON_INDEX` — 클레임 사유 선택지 인덱스 사전 지정
    - `ALLOW_REAL_PAYMENT` (`1`이면 결제 버튼 안전 차단 해제)

실행 방법 A (권장, Chrome GUI):
- `./scripts/run_scenario_chrome.sh`
- 특정 시나리오:
  - `./scripts/run_scenario_chrome.sh scenarios/naver/smoke_naver.scn`

실행 방법 B (직접 실행):
- `python3 executor/execute_scenario.py <scenario.scn>`
- 브라우저 유지 모드:
  - 실행 중 세션 유지 ping: `python3 executor/execute_scenario.py --keep-browser-alive <scenario.scn>`
  - 종료 후 브라우저 유지(Ctrl+C 종료): `python3 executor/execute_scenario.py --keep-browser-open <scenario.scn>`
- 전체 진행 이력 통합 회귀:
  - `python3 executor/execute_scenario.py scenarios/zigzag/alpha_full_history_regression.scn --continue-on-error`
- 드라이런 검증:
  - `python3 executor/execute_scenario.py --dry-run <scenario.scn>`

실행 방법 C (이미 떠있는 Chrome에 CDP 연결):
- `python3 executor/run_with_playwright.py --cdp <scenario.scn>`
- 참고: 파일명은 `run_with_playwright.py`지만 실제 구현은 Playwright가 아니라 `core.agent_browser`를 사용.

검증 포인트:
- 종료 코드가 0인지 확인
- `logs/order-agent-exec_*.log` 또는 `logs/agent-browser-runner_*.log`에 FAILED 라인이 없는지 확인
- 스크린샷 결과(`logs/result.png`, 기타 `logs/*.png`)로 최종 화면 확인

트러블슈팅:
- `agent-browser: command not found`
  - `agent-browser` 설치/경로 설정 확인
- `Chrome not found` 또는 CDP 포트 연결 실패
  - Chrome 실행 경로 확인, 필요 시 `AGENT_BROWSER_EXECUTABLE_PATH` 지정
- 요소 탐색 실패 (`Element not found`, `not visible`)
  - 페이지 DOM 변경 여부 확인 후 `.scn` selector 갱신
- 결제 버튼 차단 오류 (`CLICK confirm_payment blocked`)
  - 기본 정책 정상 동작. 실제 결제 테스트가 반드시 필요할 때만 `ALLOW_REAL_PAYMENT=1` 사용
