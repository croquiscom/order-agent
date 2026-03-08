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
- 핵심은 `services/zigzag/scripts/execute_scenario.py`가 시나리오를 파싱해 `agent-browser` CLI를 순차 호출하는 구조.
- 브라우저 컨트롤은 `agent-browser`만 사용하고 `openclaw`는 사용하지 않음.

## 2) 루트 구조
- `core/`
  - `runner.py`: `agent-browser` subprocess 래퍼 (`agent_browser()`), 실패 시 `AgentBrowserError` 발생.
  - `logger.py`: `logs/` 파일 + 콘솔 핸들러 로깅.
  - `agent_browser.py`: CDP 직접 제어 구현(웹소켓 기반). `python -m core.agent_browser ...`로 단독 실행 가능.
- `services/zigzag/`
  - `scenarios/*.scn`: Zigzag/샘플 시나리오.
  - `scripts/execute_scenario.py`: 기본 실행 엔트리포인트.
  - `scripts/generate_scenario_claude.py`: Anthropic API로 시나리오 생성.
  - `scripts/run_with_playwright.py`: 이름과 달리 Playwright가 아니라 `core.agent_browser` 사용.
- `services/naver/scenarios/*.scn`: 네이버 검증용 시나리오.
- `scripts/run_scenario_chrome.sh`: Chrome GUI 환경변수 설정 후 `execute_scenario.py` 실행.
- `tests/`: 파서/러너/로거 단위 테스트.
- `logs/`: 실행 로그/스크린샷 산출물.
- `requirements.txt`: `anthropic>=0.40.0`

## 3) 실행 흐름
1. `execute_scenario.py`가 `.scn`을 읽어 `ScenarioCommand` 리스트 생성.
2. `validate_command()`로 액션/인자/결제 안전정책 검증.
3. `to_agent_browser_args()`로 `agent-browser` CLI 인자 변환.
4. `core.runner.agent_browser()`로 subprocess 실행.
5. 로그는 `logs/order-agent-exec_YYYYMMDD_HHMMSS.log`로 기록.

## 4) 시나리오 DSL (현재 코드 기준)
허용 액션 (`execute_scenario.py`):
- `NAVIGATE <url>`
- `CLICK <selector_or_id>`
- `FILL <selector_or_id> <value...>`
- `WAIT_FOR <selector_or_id|milliseconds>`
- `CHECK <selector_or_id>`
- `PRESS <key>`
- `CHECK_URL <substring>`
- `WAIT_URL <substring>`
- `DUMP_STATE <tag>`
- `CHECK_NEW_ORDER_SHEET`

파싱 규칙:
- 빈 줄, `#` 주석 줄 무시.
- `shlex.split` 기반이라 따옴표 문자열 지원.

셀렉터 정규화:
- `@ # . [ / xpath= text= role=` 접두사가 없으면 legacy 호환으로 `@`를 자동 부여.

## 5) 안전 정책
- `CLICK confirm_payment`는 기본 차단.
- 정말 필요한 경우에만 `ALLOW_REAL_PAYMENT=1` 환경변수로 해제.
- 시나리오 생성기(`generate_scenario_claude.py`)도 동일 정책으로 차단 검증.

## 6) 주요 커맨드
- 기본 실행:
  - `python3 services/zigzag/scripts/execute_scenario.py`
- 특정 시나리오:
  - `python3 services/zigzag/scripts/execute_scenario.py <path/to/file.scn>`
- 드라이런:
  - `python3 services/zigzag/scripts/execute_scenario.py --dry-run`
- 에러 계속 진행:
  - `python3 services/zigzag/scripts/execute_scenario.py --continue-on-error`
- 오버레이 재시도 비활성화:
  - `python3 services/zigzag/scripts/execute_scenario.py --no-retry-on-overlay`
- WAIT_URL 타임아웃 설정:
  - `python3 services/zigzag/scripts/execute_scenario.py --url-wait-timeout-ms 30000 <scenario.scn>`
- Claude 시나리오 생성:
  - `python3 services/zigzag/scripts/generate_scenario_claude.py "<prompt>"`

## 7) 환경/의존성
- Python 3.12+
- 실행 시 `agent-browser` CLI가 PATH에 있어야 함.
- 시나리오 생성 시 `ANTHROPIC_API_KEY` 필요.
- 현재 작업 환경에서는 `pytest` 명령이 없어 테스트 실행 불가(설치 필요).

## 8) 변경 시 유의사항
- 시나리오 액션을 추가/변경하면 아래를 함께 맞출 것:
  - `execute_scenario.py`: `ALLOWED_ACTIONS`, 검증, CLI 변환
  - `generate_scenario_claude.py`: 액션 검증/시스템 프롬프트
  - `services/*/scenarios/*.scn`: 샘플/스모크 시나리오
  - `tests/*`: 파싱/변환/실행 테스트
- 자동화 결과 판단은 로그(`logs/*.log`)와 스크린샷(`logs/*.png`)을 함께 확인.
- 클릭이 오버레이에 가릴 수 있어 실행기는 기본적으로 `ESC` 후 1회 재시도함.
- `CLICK text=...`가 실패하면 실행기는 `find text <value> click` fallback을 1회 수행함.

## 9) 실제 브라우저 환경 테스트 가이드
브라우저 기반:
- 본 프로젝트의 실제 브라우저 테스트는 Chrome/Chromium + CDP(DevTools Protocol) 기반.
- macOS 기본 경로: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- 테스트 대상 기본 도메인: `https://alpha.zigzag.kr/`
- 브라우저 활성화 정책: auto-connect(CDP) 우선, 실패 시 실행경로 자동 탐색 후 기동

사전 준비:
- Chrome(또는 Chromium) 설치
- `agent-browser` CLI 실행 가능 상태(PATH 등록)
- 테스트 대상 시나리오 파일 준비 (`services/*/scenarios/*.scn`)
- 필요 시 환경변수로 활성화 제어:
  - `AGENT_BROWSER_AUTO_CONNECT` (기본 `1`)
  - `AGENT_BROWSER_EXECUTABLE_PATH` (수동 지정 시)
  - `ORDER_AGENT_DISABLE_BROWSER_PATH_RESOLVE` (`1`이면 자동 경로탐색 비활성화)
  - `ORDER_AGENT_CDP_PORT` (기본 `9222`)
  - `ORDER_AGENT_BROWSER_ATTACH_ONLY` (`1`이면 attach 전용)
  - `ORDER_AGENT_BROWSER_PROFILE_DIR` (전용 user-data-dir)
  - `ORDER_AGENT_BROWSER_HEADLESS`, `ORDER_AGENT_BROWSER_NO_SANDBOX`, `ORDER_AGENT_BROWSER_EXTRA_ARGS`

실행 방법 A (권장, Chrome GUI):
- `./scripts/run_scenario_chrome.sh`
- 특정 시나리오:
  - `./scripts/run_scenario_chrome.sh services/naver/scenarios/smoke_naver.scn`

실행 방법 B (직접 실행):
- `python3 services/zigzag/scripts/execute_scenario.py <scenario.scn>`
- 브라우저 유지 모드:
  - 실행 중 세션 유지 ping: `python3 services/zigzag/scripts/execute_scenario.py --keep-browser-alive <scenario.scn>`
  - 종료 후 브라우저 유지(Ctrl+C 종료): `python3 services/zigzag/scripts/execute_scenario.py --keep-browser-open <scenario.scn>`
- 전체 진행 이력 통합 회귀:
  - `python3 services/zigzag/scripts/execute_scenario.py services/zigzag/scenarios/alpha_full_history_regression.scn --continue-on-error`
- 드라이런 검증:
  - `python3 services/zigzag/scripts/execute_scenario.py --dry-run <scenario.scn>`

실행 방법 C (이미 떠있는 Chrome에 CDP 연결):
- `python3 services/zigzag/scripts/run_with_playwright.py --cdp <scenario.scn>`
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
