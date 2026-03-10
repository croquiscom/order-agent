# OrderAgent

내부망 환경에서 커머스 웹서비스 주문 플로우를 시나리오 기반으로 자동화하는 프로젝트.
브라우저 제어는 `agent-browser`만 사용하며, `openclaw`는 사용하지 않음.

## 작업 배경 및 목표

### 작업 배경
- 내부망 환경에서 커머스 웹서비스 주문 플로우 자동화 테스트 필요
- 지그재그(Zigzag)의 동적 UI/다양한 옵션으로 수동 테스트 비용 증가
- 내부망 보안 정책(외부 API 제한)과 실제 결제 방지 제약 존재
- 브라우저 자동화 + AI 시나리오 생성 방식으로 효율화 필요

### 프로젝트 목표
- 주문 흐름 자동화로 테스트 반복성 확보
- 시나리오 기반 테스트 케이스를 빠르게 실행 가능하게 설계
- Claude 연동 시나리오 생성/수정 지원
- `agent-browser` 기반 브라우저 제어로 UI 변화 대응
- 테스트 계정 사용 + 실결제 금액 발생 금지(포인트 전액 `0원` 결제 경로)로 안전성 확보
- 테스트 대상 기본 도메인: `https://alpha.zigzag.kr/`

## 디렉토리 구조

```
order-agent/
├── core/                    # runner.py, agent_browser.py, otp_reader.py, logger.py
├── executor/                # execute_scenario.py, generate_scenario_claude.py, run_with_playwright.py
├── scenarios/
│   ├── zigzag/             # Zigzag 주문/클레임 시나리오
│   ├── naver/              # 네이버 시나리오
│   └── aws/                # AWS SSO 등 유틸리티 시나리오
├── scripts/                 # run_scenario_chrome.sh
├── tests/                   # 단위 테스트
├── logs/                    # 실행 로그/스크린샷
├── docs/                    # 패턴 문서, 시나리오 목록 등
└── requirements.txt
```

## 사전 요구사항

### Python
- Python 3.12+
- 의존성 설치: `pip install -r requirements.txt`

### agent-browser

`agent-browser`는 npm 글로벌 패키지로 설치한다.

```bash
npm install -g agent-browser
```

설치 후 `agent-browser --version`으로 동작을 확인한다.

### Chrome / Chromium
- macOS 기본 경로: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- 실행 경로를 자동 탐색하므로 별도 지정 없이 Chrome이 설치되어 있으면 동작함
- 수동 지정이 필요한 경우 `AGENT_BROWSER_EXECUTABLE_PATH` 환경변수 사용

### Authenticator 확장프로그램 (OTP 읽기)

AWS SSO 등 OTP가 필요한 시나리오를 실행하려면 Chrome에 Authenticator 확장프로그램을 수동 설치해야 한다.

- 확장프로그램 ID: `bhghoamapcdpbohphigoooaddinpkbai`
- Chrome 웹스토어 또는 내부 배포 경로를 통해 설치
- 설치 후 해당 계정의 OTP를 확장프로그램에 등록해두어야 `READ_OTP` 액션이 동작함

### 시나리오 생성 (선택)
- Claude API를 이용한 시나리오 자동 생성 시 `ANTHROPIC_API_KEY` 환경변수 필요

## 테스트 계정 및 로그인

### alpha 환경 로그인 (`ENSURE_LOGIN_ALPHA`)

`ENSURE_LOGIN_ALPHA`는 시나리오 내에서 alpha.zigzag.kr에 이미 로그인되어 있는지 CDP로 확인하는 액션이다.
로그인 상태가 아닌 경우 자동으로 로그인 페이지로 이동하여 환경변수의 자격증명으로 로그인한다.

**사전 설정:**
1. `.env.example`을 복사하여 `.env` 파일 생성
2. `ALPHA_USERNAME`과 `ALPHA_PASSWORD`에 실제 테스트 계정 정보 입력

```bash
cp .env.example .env
# .env 파일을 편집하여 실제 계정 정보 입력
```

환경변수가 설정되지 않은 경우 `ENSURE_LOGIN_ALPHA` 실행 시 에러가 발생한다.

### 테스트 상품 ID
- 스토어배송: `100136725`
- 직진배송: `100100014`

테스트 계정은 포인트 전액 결제(0원 실결제) 경로만 사용한다.

## 브라우저 활성화 정책

- 기존 CDP 포트에 먼저 attach 시도 (`AGENT_BROWSER_AUTO_CONNECT=1` 기본)
- attach 실패 시 실행 경로 자동 탐색 후 브라우저 기동
- 기본 프로필 디렉터리: `~/.order-agent/browser/agent-browser-profile`
- 확장프로그램은 기본으로 허용됨 (`ORDER_AGENT_BROWSER_ENABLE_EXTENSIONS` 기본 `1`)

### 주요 환경변수

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `ALPHA_USERNAME` | (필수) | alpha.zigzag.kr 테스트 계정 이메일 |
| `ALPHA_PASSWORD` | (필수) | alpha.zigzag.kr 테스트 계정 비밀번호 |
| `AGENT_BROWSER_AUTO_CONNECT` | `1` | CDP 포트에 자동 attach 시도 |
| `AGENT_BROWSER_EXECUTABLE_PATH` | (자동탐색) | Chrome 실행 파일 경로 수동 지정 |
| `ORDER_AGENT_CDP_PORT` | `9222` | CDP 포트 번호 |
| `ORDER_AGENT_BROWSER_ATTACH_ONLY` | | `1`이면 자동 기동 금지, attach만 허용 |
| `ORDER_AGENT_BROWSER_PROFILE_DIR` | | 전용 user-data-dir 경로 |
| `ORDER_AGENT_BROWSER_HEADLESS` | | `1`이면 headless 모드 |
| `ORDER_AGENT_BROWSER_NO_SANDBOX` | | `1`이면 no-sandbox 플래그 추가 |
| `ORDER_AGENT_BROWSER_EXTRA_ARGS` | | 추가 Chrome 실행 인수 문자열 |
| `ORDER_AGENT_BROWSER_ENABLE_EXTENSIONS` | `1` | `0`이면 확장프로그램 비활성화 |
| `ORDER_AGENT_DISABLE_BROWSER_PATH_RESOLVE` | | `1`이면 자동 경로 탐색 비활성화 |
| `ORDER_AGENT_DISABLE_CDP_TAB_SANITIZE` | | `1`이면 시작 시 CDP 탭 정리 비활성화 |
| `ALLOW_REAL_PAYMENT` | | `1`이면 `CLICK confirm_payment` 차단 해제 |
| `ANTHROPIC_API_KEY` | | 시나리오 자동 생성 시 필요 |

## 실행

### 방법 A — Chrome GUI (권장)

```bash
# 기본 시나리오 실행
./scripts/run_scenario_chrome.sh

# 특정 시나리오 지정
./scripts/run_scenario_chrome.sh scenarios/zigzag/alpha_direct_buy_order_normal.scn

# 네이버 스모크 테스트
./scripts/run_scenario_chrome.sh scenarios/naver/smoke_naver.scn
```

### 방법 B — 직접 실행

```bash
# 기본 실행 (기본 시나리오)
python3 executor/execute_scenario.py

# 특정 시나리오 파일 지정
python3 executor/execute_scenario.py scenarios/zigzag/alpha_direct_buy_order_normal.scn

# --var 옵션으로 외부 값 전달
python3 executor/execute_scenario.py scenarios/zigzag/alpha_claim_cancel_by_order.scn --var order_number=123

# 드라이런 (검증만 수행, 실행 안 함)
python3 executor/execute_scenario.py --dry-run

# 오류가 나도 계속 진행
python3 executor/execute_scenario.py --continue-on-error

# 전체 회귀 테스트 (오류 계속 진행)
python3 executor/execute_scenario.py scenarios/zigzag/alpha_full_history_regression.scn --continue-on-error

# 오버레이 차단 자동 재시도(ESC) 비활성화
python3 executor/execute_scenario.py --no-retry-on-overlay <scenario.scn>

# WAIT_URL 타임아웃 조정
python3 executor/execute_scenario.py --url-wait-timeout-ms 30000 <scenario.scn>

# 빠른 실패 모드 (타임아웃 12초 + 클릭 fallback 비활성화)
python3 executor/execute_scenario.py --fast-mode <scenario.scn>

# 클릭 fallback만 비활성화
python3 executor/execute_scenario.py --disable-click-fallback <scenario.scn>

# 실행 중 브라우저 세션 유지 ping
python3 executor/execute_scenario.py --keep-browser-alive <scenario.scn>

# 시나리오 종료 후에도 브라우저 유지 (Ctrl+C로 종료)
python3 executor/execute_scenario.py --keep-browser-open <scenario.scn>
```

### 방법 C — 이미 실행 중인 Chrome에 CDP 연결

```bash
python3 executor/run_with_playwright.py --cdp <scenario.scn>
```

참고: 파일명은 `run_with_playwright.py`지만 실제 구현은 Playwright가 아니라 `core.agent_browser`를 사용한다.

### 시나리오 자동 생성 (Claude)

```bash
# 프롬프트로 시나리오 생성
python3 executor/generate_scenario_claude.py "주문 시나리오 프롬프트"

# 출력 파일 경로 지정
python3 executor/generate_scenario_claude.py "프롬프트" --output scenarios/zigzag/custom.scn
```

### AWS SSO 로그인

```bash
python3 executor/execute_scenario.py scenarios/aws/sso_login.scn --var username=<email> --var password=<pw>
```

## 주요 CLI 옵션 요약

| 옵션 | 설명 |
|---|---|
| `--dry-run` | 파싱/검증만 수행, 실제 실행 안 함 |
| `--continue-on-error` | 스텝 실패 시 중단하지 않고 계속 진행 |
| `--stop-on-scenario-fail` | 시나리오 단위 실패 시 중단 |
| `--keep-browser-open` | 시나리오 종료 후 브라우저 유지 |
| `--keep-browser-alive` | 실행 중 세션 유지 ping 활성화 |
| `--no-retry-on-overlay` | 오버레이 감지 후 ESC 재시도 비활성화 |
| `--url-wait-timeout-ms <ms>` | WAIT_URL 액션 타임아웃 (밀리초) |
| `--fast-mode` | 타임아웃 12초 + 클릭 fallback 비활성화 |
| `--disable-click-fallback` | 클릭 fallback 비활성화 |
| `--var key=value` | 시나리오 변수 외부 주입 (`{{key}}` 치환) |

## 시나리오 DSL

시나리오 파일(`.scn`)은 한 줄에 하나의 액션으로 구성된다.
빈 줄과 `#` 주석은 무시된다. 따옴표 문자열(`shlex` 기반)을 지원한다.

### 허용 액션

| 액션 | 설명 |
|---|---|
| `NAVIGATE <url>` | 지정 URL로 이동 |
| `CLICK <selector>` | 요소 클릭 |
| `FILL <selector> <value>` | 입력 필드에 값 입력 |
| `WAIT_FOR <selector\|ms>` | 요소 등장 또는 지정 시간(ms) 대기 |
| `CHECK <selector>` | 요소 존재/가시성 확인 |
| `PRESS <key>` | 키 입력 (예: `Enter`, `Escape`) |
| `CHECK_URL <substring>` | 현재 URL에 부분 문자열 포함 여부 확인 |
| `WAIT_URL <substring>` | 현재 URL이 부분 문자열을 포함할 때까지 대기 |
| `DUMP_STATE <tag>` | 진단용 상태 덤프 (텍스트 + 스크린샷) |
| `CHECK_NEW_ORDER_SHEET` | 새 주문서 ID 확인 및 캐시 갱신 |
| `READ_OTP <account_name> [var_name]` | Authenticator 확장프로그램에서 OTP 읽어 변수 저장 (기본 변수명: `otp`) |
| `ENSURE_LOGIN_ALPHA` | alpha.zigzag.kr 로그인 상태 확인, 미로그인 시 로그인 페이지로 이동 |

### 셀렉터 작성 가이드

안정성이 높은 순서로 사용을 권장한다.

1. `role=textbox`, `role=button` — Playwright ARIA role 셀렉터. UI 변경에 강함.
2. `button[type=submit]`, `input[name=...]` — CSS 속성 셀렉터. ID보다 안정적.
3. `#fixed-id` — 고정 ID가 있는 경우.
4. `text=...` — 최후 수단. 부분 일치로 의도치 않은 요소 매칭 위험.

주의: 동적으로 생성되는 ID (`#awsui-input-0` 등)는 렌더링마다 변할 수 있으므로 사용하지 않는다.

### 변수 치환

`--var key=value`로 주입한 값은 시나리오 내 `{{key}}` 형태로 참조한다.

```
FILL input[name=orderNumber] {{order_number}}
```

### 예시 시나리오

```
# alpha 직진배송 주문 생성
ENSURE_LOGIN_ALPHA
NAVIGATE https://alpha.zigzag.kr/product/100100014
CLICK role=button[name="바로구매"]
WAIT_URL /order/sheet
CHECK_NEW_ORDER_SHEET
CLICK button[type=submit]
```

## 안전 정책

- 테스트 계정만 사용 (실 결제 금액 발생 금지)
- 포인트 전액 결제 경로만 사용하여 0원 실결제 유지
- `CLICK confirm_payment`는 기본으로 차단됨
- 실제 결제 테스트가 반드시 필요한 경우에만 `ALLOW_REAL_PAYMENT=1` 환경변수를 설정하여 실행
- 인증 정보는 환경변수로 관리하며 시나리오 파일에 하드코딩하지 않음

## 로깅

- 실행 로그: `logs/order-agent-exec_YYYYMMDD_HHMMSS.log`
- 실패 시 자동 스크린샷: `logs/failed_line_<line>_YYYYMMDD_HHMMSS.png`
- 상태 덤프(`DUMP_STATE`): `logs/diag_<tag>_YYYYMMDD_HHMMSS.txt` / `.png`
- 마지막 주문서 ID 캐시: `logs/last_order_sheet_id.txt` (`CHECK_NEW_ORDER_SHEET` 갱신)

## 검증 포인트

- 종료 코드 `0` 확인
- `logs/order-agent-exec_*.log`에 `FAILED` 라인 없음 확인
- `logs/result.png` 등 스크린샷으로 최종 화면 확인

## 트러블슈팅

**`agent-browser: command not found`**
- `npm install -g agent-browser` 후 `agent-browser --version` 확인

**`Chrome not found` 또는 CDP 포트 연결 실패**
- Chrome 설치 여부 확인
- 필요 시 `AGENT_BROWSER_EXECUTABLE_PATH`로 경로 수동 지정

**요소 탐색 실패 (`Element not found`, `not visible`)**
- 페이지 DOM 변경 여부 확인 후 `.scn` 셀렉터 갱신

**특수문자 입력 불량 (비밀번호 등)**
- `agent-browser fill`의 특수문자 이스케이프 버그로 인해 `!` 등이 `\!`로 변환될 수 있음
- 실행기는 `FILL` 액션을 CDP `Input.dispatchKeyEvent` 방식(`_cdp_direct_fill`)으로 처리하여 우회함

**`CLICK confirm_payment blocked` 오류**
- 기본 안전 정책이 정상 동작하는 것. 실제 결제 테스트가 반드시 필요한 경우에만 `ALLOW_REAL_PAYMENT=1` 사용

**OTP 읽기 실패 (`READ_OTP`)**
- Authenticator 확장프로그램(ID: `bhghoamapcdpbohphigoooaddinpkbai`)이 Chrome에 설치되어 있는지 확인
- 확장프로그램에 해당 계정 OTP가 등록되어 있는지 확인
- `ORDER_AGENT_BROWSER_ENABLE_EXTENSIONS=1` (기본값)이 설정되어 있는지 확인

## 참조 문서

- `docs/alpha_checkout_e2e_scenario.md`: 주문 E2E 상세 절차
- `docs/scenarios.md`: 시나리오 인벤토리 (단일 소스)
- `docs/input_interaction_patterns.md`: 클레임 UI 입력 패턴
- `docs/exchange_stabilization_plan.md`: 교환 안정화 계획
