# 수동 설정 가이드

Claude Code를 사용하지 않는 경우 이 가이드를 따라 직접 환경을 설정한다.

---

## 1. 사전 요구사항

| 항목 | 최소 버전 | 확인 명령 |
|---|---|---|
| Python | 3.12+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| Chrome / Chromium | 최신 안정 버전 | — |

---

## 2. 설치

```bash
# 1. 저장소 클론
git clone git@github.com:croquiscom/order-agent.git
cd order-agent

# 2. Python 의존성 설치
pip install -r requirements.txt

# 3. agent-browser 설치
npm install -g agent-browser
agent-browser --version

# 4. 환경변수 설정
cp .env.example .env
# .env 파일을 편집하여 실제 값 입력
```

---

## 3. 환경변수 설정

`.env` 파일에 아래 항목을 설정한다.

**필수**

| 항목 | 설명 |
|---|---|
| `ALPHA_USERNAME` | alpha.zigzag.kr 테스트 계정 이메일 |
| `ALPHA_PASSWORD` | alpha.zigzag.kr 테스트 계정 비밀번호 |

**선택**

| 항목 | 설명 |
|---|---|
| `ANTHROPIC_API_KEY` | AI 시나리오 자동 생성 시 필요 |

`.env` 파일 예시:

```
ALPHA_USERNAME=test@example.com
ALPHA_PASSWORD=your_password_here
ANTHROPIC_API_KEY=sk-ant-...
```

자격증명은 `.env` 파일에만 보관하고 시나리오 파일(`.scn`)에 하드코딩하지 않는다.

---

## 4. Chrome 설정

### 경로 확인

agent-browser는 Chrome 실행 파일을 자동으로 탐색한다.

- macOS 기본 경로: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- 자동 탐색에 실패하면 `AGENT_BROWSER_EXECUTABLE_PATH` 환경변수로 경로를 직접 지정한다.

```bash
export AGENT_BROWSER_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

### CDP 포트 확인

기본 CDP 포트는 `9222`이다. 충돌이 있을 경우 `ORDER_AGENT_CDP_PORT` 환경변수로 변경한다.

```bash
export ORDER_AGENT_CDP_PORT=9223
```

### Authenticator 확장프로그램 설치 (OTP 필요 시)

AWS SSO 등 OTP가 필요한 시나리오를 실행하려면 Chrome에 Authenticator 확장프로그램을 설치해야 한다.

- 확장프로그램 ID: `bhghoamapcdpbohphigoooaddinpkbai`
- Chrome 웹스토어 또는 내부 배포 경로를 통해 설치
- 설치 후 해당 계정의 OTP 시드를 확장프로그램에 등록

---

## 5. 첫 시나리오 실행

```bash
# 드라이런 (브라우저 없이 파싱/검증만 수행)
python3 executor/execute_scenario.py --dry-run scenarios/zigzag/alpha_direct_buy_complete_normal.scn

# 실제 실행
python3 executor/execute_scenario.py scenarios/zigzag/alpha_direct_buy_complete_normal.scn
```

---

## 6. 주요 실행 방법

### 방법 A — Chrome GUI (권장)

```bash
# 기본 시나리오 실행
./scripts/run_scenario_chrome.sh

# 특정 시나리오 지정
./scripts/run_scenario_chrome.sh scenarios/zigzag/alpha_direct_buy_order_normal.scn
```

### 방법 B — 직접 실행

```bash
# 특정 시나리오 파일 지정
python3 executor/execute_scenario.py scenarios/zigzag/alpha_direct_buy_order_normal.scn

# 외부 값 전달 (--var)
python3 executor/execute_scenario.py scenarios/zigzag/alpha_claim_cancel_by_order.scn --var order_number=123

# 오류가 나도 계속 진행
python3 executor/execute_scenario.py --continue-on-error scenarios/zigzag/alpha_full_history_regression.scn
```

### 방법 C — 이미 실행 중인 Chrome에 CDP 연결

```bash
python3 executor/run_with_playwright.py --cdp <scenario.scn>
```

참고: 파일명은 `run_with_playwright.py`지만 실제 구현은 `core.agent_browser`를 사용한다.

### AWS SSO 로그인

```bash
# 환경변수로 자격증명 전달 (CLI 노출 방지)
export AWS_SSO_USERNAME="<email>"
read -s AWS_SSO_PASSWORD
python3 executor/execute_scenario.py scenarios/aws/sso_login.scn \
  --var username="${AWS_SSO_USERNAME}" --var password="${AWS_SSO_PASSWORD}"
```

---

## 7. 검증 포인트

실행 후 아래를 확인한다.

- 종료 코드가 `0`인지 확인
- `logs/order-agent-exec_*.log`에 `FAILED` 라인이 없는지 확인
- `logs/result.png` 등 스크린샷으로 최종 화면 확인

```bash
# 최근 실행 로그 확인
ls -lt logs/*.log | head -5
```

---

## 8. 트러블슈팅

**`agent-browser: command not found`**

`npm install -g agent-browser` 후 `agent-browser --version`으로 동작을 확인한다.
npm 글로벌 bin 경로가 `PATH`에 포함되어 있는지 확인한다.

```bash
npm bin -g   # 글로벌 bin 경로 확인
```

**`Chrome not found` 또는 CDP 포트 연결 실패**

Chrome이 설치되어 있는지 확인한다. 경로 탐색에 실패하면 `AGENT_BROWSER_EXECUTABLE_PATH`를 직접 지정한다.
이미 실행 중인 Chrome이 CDP 포트를 점유하고 있는지 확인한다.

```bash
lsof -i :9222   # CDP 포트 사용 여부 확인
```

**요소 탐색 실패 (`Element not found`, `not visible`)**

페이지 DOM이 변경된 경우 `.scn` 파일의 셀렉터를 갱신해야 한다.
`DUMP_STATE` 액션을 임시로 삽입하여 현재 DOM 구조를 확인한다.

**특수문자 입력 불량 (비밀번호 등)**

실행기는 `FILL` 액션을 CDP `Input.dispatchKeyEvent` 방식으로 처리하여 특수문자를 한 글자씩 전송한다. `agent-browser fill`의 특수문자 이스케이프 버그와 무관하게 동작한다.

**`CLICK confirm_payment blocked` 오류**

기본 안전 정책이 정상 동작하는 것이다. 실제 결제 테스트가 반드시 필요한 경우에만 `ALLOW_REAL_PAYMENT=1` 환경변수를 설정하여 실행한다.

**OTP 읽기 실패 (`READ_OTP`)**

아래를 순서대로 확인한다.

1. Authenticator 확장프로그램(ID: `bhghoamapcdpbohphigoooaddinpkbai`)이 Chrome에 설치되어 있는지 확인
2. 확장프로그램에 해당 계정 OTP 시드가 등록되어 있는지 확인
3. `ORDER_AGENT_BROWSER_DISABLE_EXTENSIONS` 환경변수가 설정되어 있지 않은지 확인 — 기본값은 확장프로그램 활성 상태

**`websocket-client` 모듈 오류**

OTP 읽기 기능에는 `websocket-client` 패키지가 필요하다.

```bash
pip install websocket-client
```

**환경변수가 적용되지 않는 경우**

`.env` 파일이 프로젝트 루트에 있는지 확인한다. 실행기는 자동으로 `.env`를 로드한다. 또는 셸 세션에 직접 export 한다.

```bash
export ALPHA_USERNAME=test@example.com
export ALPHA_PASSWORD=your_password_here
```
