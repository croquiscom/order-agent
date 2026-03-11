# OrderAgent

**OrderAgent** — CDP 기반 브라우저 에이전트 프레임워크.
시나리오(DSL)로 웹 브라우저를 제어하여 다양한 브라우저 에이전트 기능을 제공한다.

- 주문 E2E 테스트 자동화 — 커머스 주문/클레임 플로우 자동 검증
- SSO 로그인 자동화 — AWS SSO 등 MFA(OTP) 포함 인증 플로우 자동화
- DSL 기반 시나리오 — `.scn` 파일로 테스트 시나리오 정의
- CDP 브라우저 제어 — Chrome DevTools Protocol 직접 제어
- AI 시나리오 생성 — Claude API 연동 시나리오 자동 생성
- 안전 정책 — 실결제 차단, 테스트 계정 분리

---

## 빠른 시작

**Claude Code 사용자**

`/setup` 스킬로 환경을 한번에 검증/설정할 수 있다. 이후 `/list-scenarios`로 시나리오 목록을 확인하고 `/run-scenario`로 실행한다.

```
/setup
```

**수동 설정**

[수동 설정 가이드](docs/manual-setup-guide.md) 참조.

---

## 아키텍처

```
.scn (시나리오) → Parser → Executor → CDP → Chrome → Logs
```

```
order-agent/
├── core/          # 브라우저 제어 엔진 (runner.py, agent_browser.py, otp_reader.py, logger.py)
├── executor/      # 시나리오 실행 엔진 (execute_scenario.py, generate_scenario_claude.py)
├── scenarios/
│   ├── zigzag/    # Zigzag 주문/클레임 시나리오
│   ├── naver/     # 네이버 시나리오
│   └── aws/       # AWS SSO 등 유틸리티 시나리오
├── scripts/       # 실행 스크립트
├── tests/         # 단위 테스트
├── logs/          # 실행 로그/스크린샷
└── docs/          # 참조 문서
```

---

## 기능

### 브라우저 제어 엔진

- CDP 웹소켓 직접 제어
- Chrome 자동 탐색/기동/연결 (launch, attach, cdp 모드)
- 프로세스 라이프사이클 관리
- 탭 관리 및 정리
- 헤드리스/샌드박스/확장프로그램 옵션

### 시나리오 DSL 엔진

- `.scn` 파일 파싱 (shlex 기반, 주석/빈줄 처리)
- 액션 검증 및 셀렉터 정규화
- 변수 치환 (`--var key=value` → `{{key}}`)
- 드라이런 검증

### 웹 상호작용

- 네비게이션, 클릭, 입력, 키 입력
- CDP 직접 입력 (특수문자 React SPA 호환)
- URL 검증/대기
- JavaScript 실행 (EVAL)
- 스냅샷 기반 요소 탐색 (ARIA role, label, ref)

### Self-Heal (자동 복구)

- 오버레이 감지 → ESC 후 재시도
- 클릭 실패 → 텍스트 기반 fallback
- 퍼지 텍스트 매칭 (65% 유사도 임계값)
- upstream 오류(502) 자동 재시도
- 네비게이션 컨텍스트 파괴 감지 → 자동 재시도

### 인증/로그인 자동화

- 로그인 상태 확인 및 자동 로그인
- OTP 자동 읽기 (Authenticator 확장프로그램 CDP 제어)
- MFA 플로우 지원

### 진단/증적 수집

- 실행 로그 (파일 + 콘솔, 타임스탬프)
- 실패 시 자동 스크린샷
- 상태 덤프 (`DUMP_STATE` — 텍스트 + 스크린샷)
- 모달/에러 메시지 추출
- Self-heal 이력 추적
- 스텝별 실행 리포트

### 안전 정책

- 실결제 버튼 클릭 기본 차단
- 생성 시나리오에도 동일 차단 적용
- 환경변수 기반 자격증명 관리
- `EXPECT_FAIL`로 예상 실패 검증

### AI 시나리오 생성

- Claude API 연동 자동 생성
- 생성 결과 액션/안전 검증

---

## 시나리오 DSL 레퍼런스

시나리오 파일(`.scn`)은 한 줄에 하나의 액션으로 구성된다.
빈 줄과 `#` 주석은 무시된다. 따옴표 문자열(`shlex` 기반)을 지원한다.

### 기본 액션

| 액션 | 설명 |
|---|---|
| `NAVIGATE <url>` | URL 이동 |
| `CLICK <selector>` | 요소 클릭 |
| `FILL <selector> <value>` | 입력 필드에 값 입력 |
| `WAIT_FOR <selector\|ms>` | 요소 대기 또는 지연 |
| `CHECK <selector>` | 요소 존재 확인 |
| `PRESS <key>` | 키 입력 |
| `CHECK_URL <substring>` | URL 포함 여부 확인 |
| `CHECK_NOT_URL <substring>` | URL 미포함 확인 |
| `WAIT_URL <substring>` | URL 포함 대기 |
| `DUMP_STATE <tag>` | 상태 덤프 |
| `EVAL <javascript>` | JavaScript 실행 |
| `READ_OTP <account> [var]` | OTP 읽기 (기본 변수명: `otp`) |
| `EXPECT_FAIL [pattern]` | 다음 액션 실패 예상 |

### 셀렉터 우선순위

안정성이 높은 순서로 사용한다.

1. `role=textbox`, `role=button` — ARIA role 셀렉터, UI 변경에 강함
2. `button[type=submit]`, `input[name=...]` — CSS 속성 셀렉터, ID보다 안정적
3. `#fixed-id` — 고정 ID가 있는 경우
4. `text=...` — 최후 수단, 부분 일치로 의도치 않은 요소 매칭 위험

동적으로 생성되는 ID(`#awsui-input-0` 등)는 렌더링마다 변할 수 있으므로 사용하지 않는다.

### 변수 치환

`--var key=value`로 주입한 값은 시나리오 내 `{{key}}` 형태로 참조한다.

```
FILL input[name=orderNumber] {{order_number}}
```

---

## 도메인 확장

### 커머스 E2E 테스트 — Zigzag

| 액션 | 설명 |
|---|---|
| `ENSURE_LOGIN_ALPHA` | alpha 로그인 확인/자동 로그인 |
| `CHECK_NEW_ORDER_SHEET` | 주문서 생성 확인 |
| `CLICK_SNAPSHOT_TEXT <text>` | 퍼지 텍스트 매칭 클릭 |
| `CLICK_ORDER_DETAIL_WITH_ACTION <action>` | 주문 상세 액션 버튼 클릭 |
| `APPLY_ORDER_STATUS_FILTER <status>` | 주문 상태 필터 적용 |
| `SUBMIT_CANCEL_REQUEST <reason>` | 취소 요청 |
| `SUBMIT_RETURN_REQUEST <reason>` | 반품 요청 |
| `SUBMIT_EXCHANGE_REQUEST <reason>` | 교환 요청 |
| `CHECK_PAYMENT_RESULT` | 결제 결과 확인 |

**시나리오 카테고리**

- 주문 생성/완료 — 바로구매, 장바구니 (스토어배송/직진배송)
- 클레임 — 취소/반품/교환
- 클레임 정책 차단 — 정책 위반 차단 검증
- 결제/포인트 예외 — 포인트 부족, 결제 차단, 결제 고착
- 회귀 테스트 — 전체 플로우 통합 검증

테스트 상품 ID: 스토어배송 `100136725`, 직진배송 `100100014`.

### SSO 로그인 자동화 — AWS

AWS SSO 포털 로그인 + OTP 자동 입력.

```bash
# 환경변수로 자격증명 전달 (CLI 노출 방지)
export AWS_SSO_USERNAME="<email>"
read -s AWS_SSO_PASSWORD
python3 executor/execute_scenario.py scenarios/aws/sso_login.scn \
  --var username="${AWS_SSO_USERNAME}" --var password="${AWS_SSO_PASSWORD}"
```

---

## CLI 옵션

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

---

## 환경변수

**브라우저**

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `AGENT_BROWSER_AUTO_CONNECT` | `1` | CDP 포트에 자동 attach 시도 |
| `AGENT_BROWSER_EXECUTABLE_PATH` | (자동탐색) | Chrome 실행 파일 경로 수동 지정 |
| `ORDER_AGENT_BROWSER_ATTACH_ONLY` | | `1`이면 자동 기동 금지, attach만 허용 |
| `ORDER_AGENT_BROWSER_PROFILE_DIR` | | 전용 user-data-dir 경로 |
| `ORDER_AGENT_BROWSER_HEADLESS` | | `1`이면 headless 모드 |
| `ORDER_AGENT_BROWSER_NO_SANDBOX` | | `1`이면 no-sandbox 플래그 추가 |
| `ORDER_AGENT_BROWSER_EXTRA_ARGS` | | 추가 Chrome 실행 인수 문자열 |
| `ORDER_AGENT_BROWSER_DISABLE_EXTENSIONS` | | `1`이면 확장프로그램 비활성화 |
| `ORDER_AGENT_DISABLE_BROWSER_PATH_RESOLVE` | | `1`이면 자동 경로 탐색 비활성화 |
| `ORDER_AGENT_DISABLE_CDP_TAB_SANITIZE` | | `1`이면 시작 시 CDP 탭 정리 비활성화 |

**CDP**

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `ORDER_AGENT_CDP_PORT` | `9222` | CDP 포트 번호 |

**인증**

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `ALPHA_USERNAME` | (필수) | alpha.zigzag.kr 테스트 계정 이메일 |
| `ALPHA_PASSWORD` | (필수) | alpha.zigzag.kr 테스트 계정 비밀번호 |
| `ANTHROPIC_API_KEY` | | 시나리오 자동 생성 시 필요 |

**안전**

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `ALLOW_REAL_PAYMENT` | | `1`이면 `CLICK confirm_payment` 차단 해제 |

---

## 트러블슈팅

**`agent-browser: command not found`**
`npm install -g agent-browser` 후 `agent-browser --version` 확인.

**`Chrome not found` 또는 CDP 포트 연결 실패**
Chrome 설치 여부 확인. 필요 시 `AGENT_BROWSER_EXECUTABLE_PATH`로 경로 수동 지정.

**요소 탐색 실패 (`Element not found`, `not visible`)**
페이지 DOM 변경 여부 확인 후 `.scn` 셀렉터 갱신.

**특수문자 입력 불량 (비밀번호 등)**
실행기는 `FILL` 액션을 CDP `Input.dispatchKeyEvent` 방식(`_cdp_direct_fill`)으로 처리하여 `agent-browser` 특수문자 이스케이프 버그를 우회한다.

**`CLICK confirm_payment blocked` 오류**
기본 안전 정책이 정상 동작하는 것. 실제 결제 테스트가 반드시 필요한 경우에만 `ALLOW_REAL_PAYMENT=1` 사용.

**OTP 읽기 실패 (`READ_OTP`)**
Authenticator 확장프로그램(ID: `bhghoamapcdpbohphigoooaddinpkbai`)이 Chrome에 설치되어 있는지 확인. 확장프로그램에 해당 계정 OTP가 등록되어 있는지 확인. `ORDER_AGENT_BROWSER_DISABLE_EXTENSIONS`가 설정되어 있지 않은지 확인 — 기본값은 확장프로그램 활성 상태.

---

## Claude Code 스킬

| 스킬 | 설명 |
|---|---|
| `/setup` | 환경 검증/설정 |
| `/list-scenarios` | 시나리오 목록 |
| `/run-scenario` | 시나리오 실행 |
| `/new-scenario` | 시나리오 생성 |
| `/validate-scenario` | 시나리오 검증 |
| `/analyze-failure` | 실패 분석 |
| `/check-logs` | 로그 확인 |
| `/clean-logs` | 로그 정리 |
| `/browser-status` | 브라우저 상태 확인 |
| `/commit` | 변경 분석 → 자동 커밋 |
| `/create-pr` | PR 자동 생성 |
| `/update-pr` | 기존 PR 업데이트 |

---

## 참조 문서

- [`docs/manual-setup-guide.md`](docs/manual-setup-guide.md) — 수동 설정 가이드
- [`docs/scenarios.md`](docs/scenarios.md) — 시나리오 인벤토리
- [`docs/input_interaction_patterns.md`](docs/input_interaction_patterns.md) — 클레임 UI 입력 패턴
- [`docs/exchange_stabilization_plan.md`](docs/exchange_stabilization_plan.md) — 교환 안정화 계획
- [`docs/alpha_checkout_e2e_scenario.md`](docs/alpha_checkout_e2e_scenario.md) — 주문 E2E 상세 절차
