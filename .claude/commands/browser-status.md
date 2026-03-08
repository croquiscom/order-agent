# /browser-status - 브라우저/CDP 상태 확인

## 목적
시나리오 실행 전 Chrome 브라우저와 CDP(Chrome DevTools Protocol) 연결 상태를 진단한다.
"agent-browser not found"나 "CDP 연결 실패" 같은 문제를 사전에 파악한다.

## 사용 시점
- 시나리오 실행 전 환경 점검
- CDP 연결 오류 발생 시 진단
- 브라우저가 제대로 떠 있는지 확인할 때

## 실행 방법

아래 항목을 순서대로 점검하고 결과를 보고한다:

1. **agent-browser CLI 확인**
   ```bash
   which agent-browser && agent-browser --version
   ```
   - 없으면: "agent-browser가 PATH에 없습니다" 경고

2. **Chrome 실행 파일 확인**
   ```bash
   ls "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" 2>/dev/null
   ```
   - `AGENT_BROWSER_EXECUTABLE_PATH` 환경변수도 확인

3. **CDP 포트 연결 확인**
   - 기본 포트: 9222 (`ORDER_AGENT_CDP_PORT` 환경변수 확인)
   ```bash
   curl -s http://127.0.0.1:9222/json 2>/dev/null
   ```

4. **활성 탭 목록** (CDP 연결 시)
   - 탭 수, 각 탭의 URL과 타이틀 표시
   - alpha.zigzag.kr 탭이 있는지 확인

5. **환경변수 상태**
   - `ORDER_AGENT_CDP_PORT`
   - `ORDER_AGENT_BROWSER_ATTACH_ONLY`
   - `AGENT_BROWSER_AUTO_CONNECT`
   - `AGENT_BROWSER_EXECUTABLE_PATH`

6. **진단 요약**
   - 모든 항목 통과: "Ready - 시나리오 실행 가능"
   - 일부 실패: 문제 항목과 해결 방법 안내

## 예시
- `/browser-status` — 전체 상태 점검
