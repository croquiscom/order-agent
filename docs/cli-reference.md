# CLI 레퍼런스

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
Authenticator 확장프로그램(ID: `bhghoamapcdpbohphigoooaddinpkbai`)이 Chrome에 설치되어 있는지 확인. 확장프로그램에 해당 계정 OTP가 등록되어 있는지 확인. `ORDER_AGENT_BROWSER_DISABLE_EXTENSIONS`가 설정되어 있지 않은지 확인.
