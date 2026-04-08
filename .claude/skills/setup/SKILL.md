---
name: setup
description: "프로젝트 초기 설정 및 환경 검증. 클론 직후 실행하여 의존성, 환경변수, 브라우저 등을 한번에 확인/설정. Use when: 셋업, setup, 초기 설정, 환경 설정, 처음 설정."
---

# 프로젝트 초기 설정 (Setup)

프로젝트를 처음 클론한 사용자를 위한 환경 검증 및 설정 스킬.
각 단계를 순차 실행하며, 실패 항목은 해결 방법을 안내한다.

**When to Use:** 프로젝트 최초 클론 후, 환경 이전 후, 새 팀원 온보딩
**Not for:** 시나리오 실행 → `run-scenario` | 브라우저 상태만 확인 → `browser-status`

---

## Execution Steps

### Step 1. Python 버전 확인

```bash
python3 --version
```

- 3.12 이상이면 PASS
- 미만이면: "Python 3.12+ 필요. `brew install python@3.12` 또는 `pyenv install 3.12`"

### Step 2. pip 의존성 설치

```bash
pip3 install -r requirements.txt
```

- 성공하면 PASS
- 실패하면: 에러 메시지 표시 및 수동 설치 안내

### Step 3. agent-browser CLI 확인

```bash
which agent-browser 2>/dev/null && agent-browser --version 2>/dev/null
```

- 있으면 PASS (버전 표시)
- 없으면: "agent-browser가 PATH에 없습니다. `npm install -g @anthropic/agent-browser` 로 설치하세요."

### Step 4. .env 파일 설정

1. `.env` 파일 존재 여부 확인
2. 없으면 `.env.example`에서 복사:
   ```bash
   cp .env.example .env
   ```
3. `ZIGZAG_ALPHA_USERNAME`과 `ZIGZAG_ALPHA_PASSWORD`가 플레이스홀더 상태인지 확인
4. 플레이스홀더면: 사용자에게 실제 값 입력 요청 (AskUserQuestion 사용)
5. 값이 입력되면 `.env` 파일 업데이트

### Step 5. Chrome/Chromium 설치 확인

```bash
ls "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" 2>/dev/null || \
ls "/Applications/Chromium.app/Contents/MacOS/Chromium" 2>/dev/null || \
which google-chrome 2>/dev/null || \
which chromium 2>/dev/null
```

- 있으면 PASS (경로 표시)
- 없으면: "Chrome 또는 Chromium을 설치하세요."
- `AGENT_BROWSER_EXECUTABLE_PATH` 환경변수가 설정되어 있으면 해당 경로도 확인

### Step 6. CDP 연결 테스트 (선택)

```bash
curl -s --connect-timeout 2 http://127.0.0.1:9222/json 2>/dev/null
```

- 연결 성공: PASS (활성 탭 수 표시)
- 연결 실패: "Chrome이 실행 중이 아니거나 CDP 포트가 열려있지 않습니다. 시나리오 실행 시 자동으로 브라우저가 기동됩니다." (WARNING, 비차단)

### Step 7. 드라이런 검증

기본 시나리오를 드라이런으로 실행하여 파싱/검증이 통과하는지 확인:

```bash
python3 executor/execute_scenario.py --dry-run scenarios/zigzag/alpha_direct_buy_order_normal.scn
```

- 종료 코드 0이면 PASS
- 실패하면: 에러 내용 표시

### Step 8. 결과 요약

모든 단계 결과를 테이블로 요약 출력:

| 단계 | 항목 | 결과 |
|---|---|---|
| 1 | Python 3.12+ | PASS / FAIL |
| 2 | pip 의존성 | PASS / FAIL |
| 3 | agent-browser | PASS / FAIL |
| 4 | .env 설정 | PASS / FAIL |
| 5 | Chrome | PASS / FAIL |
| 6 | CDP 연결 | PASS / SKIP |
| 7 | 드라이런 | PASS / FAIL |

- 모든 필수 항목 PASS: "Setup 완료! `python3 executor/execute_scenario.py` 로 시나리오를 실행하세요."
- FAIL 항목 존재: 실패 항목별 해결 방법 재안내

---

## 예시

- `/setup` - 전체 초기 설정 및 검증

---

**Related Skills:**
- [browser-status](../browser-status/SKILL.md) - 브라우저/CDP 상태 확인
- [run-scenario](../run-scenario/SKILL.md) - 시나리오 실행
- [list-scenarios](../list-scenarios/SKILL.md) - 시나리오 목록
