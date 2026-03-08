# OrderAgent

내부망 환경에서 커머스 웹서비스 주문 플로우를 자동화하는 프로젝트.
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
- 브라우저 제어 방식 단일화: `agent-browser` 전용 운영

## 구조

```
order-agent/
├── services/zigzag/
│   ├── scenarios/       # .scn 시나리오 파일
│   └── scripts/         # 실행/생성 스크립트
├── core/                # 공통 실행기, 로깅
├── logs/                # 실행 로그
```

## 사전 요구사항

- Python 3.12+
- agent-browser CLI 설치 및 내부망 Chromium 실행 가능
- (시나리오 생성 시) `ANTHROPIC_API_KEY` 환경변수

## 브라우저 활성화 정책

- 기존 브라우저(CDP)에 먼저 attach 시도 (`AGENT_BROWSER_AUTO_CONNECT=1` 기본)
- attach 실패 시 실행 경로 자동 해결 후 브라우저 기동
- 기본 프로필 디렉터리: `~/.order-agent/browser/agent-browser-profile`

환경변수:
- `AGENT_BROWSER_AUTO_CONNECT` (기본 `1`)
- `AGENT_BROWSER_EXECUTABLE_PATH` (필요 시 수동 지정)
- `ORDER_AGENT_DISABLE_BROWSER_PATH_RESOLVE` (`1`이면 자동 실행경로 탐색 비활성화)
- `ORDER_AGENT_CDP_PORT` (기본 `9222`)
- `ORDER_AGENT_BROWSER_ATTACH_ONLY` (`1`이면 자동 기동 금지, attach만 허용)
- `ORDER_AGENT_BROWSER_PROFILE_DIR` (전용 user-data-dir 경로)
- `ORDER_AGENT_BROWSER_HEADLESS` (`1`이면 headless)
- `ORDER_AGENT_BROWSER_NO_SANDBOX` (`1`이면 no-sandbox)
- `ORDER_AGENT_BROWSER_EXTRA_ARGS` (추가 Chrome args 문자열)
- `ORDER_AGENT_BROWSER_ENABLE_EXTENSIONS` (`1`이면 확장프로그램 활성화, 기본은 비활성화)
- `ORDER_AGENT_DISABLE_CDP_TAB_SANITIZE` (`1`이면 시작 시 CDP 탭 정리 비활성화)

## 실행

```bash
# 시나리오 실행
python3 services/zigzag/scripts/execute_scenario.py

# 특정 시나리오 파일 지정
python3 services/zigzag/scripts/execute_scenario.py path/to/custom.scn

# alpha PDP 직행 주문 생성 완료 — 스토어배송(상품: 100136725)
python3 services/zigzag/scripts/execute_scenario.py services/zigzag/scenarios/alpha_direct_buy_complete_normal.scn --continue-on-error

# 오리지널 Chrome GUI로 실행(기본: alpha_direct_buy_complete_normal.scn)
./scripts/run_scenario_chrome.sh

# 오리지널 Chrome GUI로 특정 시나리오 실행
./scripts/run_scenario_chrome.sh services/naver/scenarios/smoke_naver.scn

# 드라이런(검증만 수행)
python3 services/zigzag/scripts/execute_scenario.py --dry-run

# 실패가 나도 계속 진행
python3 services/zigzag/scripts/execute_scenario.py --continue-on-error

# 오버레이 차단 자동 재시도(ESC) 비활성화
python3 services/zigzag/scripts/execute_scenario.py --no-retry-on-overlay

# WAIT_URL 액션 타임아웃 조정
python3 services/zigzag/scripts/execute_scenario.py --url-wait-timeout-ms 30000 <scenario.scn>

# 빠른 실패 모드(권장 디버깅): 타임아웃 12초 + 클릭 fallback 비활성화
python3 services/zigzag/scripts/execute_scenario.py --fast-mode <scenario.scn>

# 클릭 fallback만 비활성화
python3 services/zigzag/scripts/execute_scenario.py --disable-click-fallback <scenario.scn>

# 실행 중 브라우저 세션 유지 ping 활성화
python3 services/zigzag/scripts/execute_scenario.py --keep-browser-alive <scenario.scn>

# 시나리오 종료 후에도 브라우저 유지(Ctrl+C 종료)
python3 services/zigzag/scripts/execute_scenario.py --keep-browser-open <scenario.scn>

# Claude로 시나리오 자동 생성
python3 services/zigzag/scripts/generate_scenario_claude.py "주문 시나리오 프롬프트"

# 생성 결과 파일 지정
python3 services/zigzag/scripts/generate_scenario_claude.py "프롬프트" --output services/zigzag/scenarios/custom.scn
```

## 안전 정책

- 테스트 계정만 사용 (실제 결제 금액 발생 X)
- 인증 정보는 환경 변수로 관리
- DOM 요소 변경 시 시나리오 파일 업데이트 필요
- 테스트 대상 기본 도메인은 `https://alpha.zigzag.kr/`
- 기본 정책상 `CLICK confirm_payment` 명령은 차단됨
- 정말 필요한 경우에만 `ALLOW_REAL_PAYMENT=1` 설정 후 실행

## 로깅

- 실행 로그는 `logs/` 디렉터리에 저장
- 실행기: `order-agent-exec_YYYYMMDD_HHMMSS.log`
- 실패 시 자동 스크린샷: `logs/failed_line_<line>_YYYYMMDD_HHMMSS.png`
- 상태 덤프(`DUMP_STATE`): `logs/diag_<tag>_YYYYMMDD_HHMMSS.txt/.png`
- 직전 실행 주문서 ID 캐시: `logs/last_order_sheet_id.txt` (`CHECK_NEW_ORDER_SHEET` 사용 시 갱신)

## 테스트 문서

- 상세 절차 문서: `docs/alpha_checkout_e2e_scenario.md`
- 시나리오 인벤토리(목록 단일 소스): `docs/scenarios.md`
- 주문 생성 시 orderNumber 비교 시나리오: `SAVE_ORDER_NUMBER`, `CHECK_ORDER_NUMBER_CHANGED` 사용
