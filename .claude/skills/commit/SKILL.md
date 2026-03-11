---
name: commit
description: "Conventional Commits 형식으로 Git 커밋 생성. Use when: 커밋해줘, 반영해, commit, 변경사항 저장."
---

# Smart Commit

Conventional Commits 형식으로 Git 커밋을 생성한다.

**When to Use:** "커밋해줘", "반영해", "commit", 변경사항 저장
**Not for:** PR 생성 (-> `create-pr`)

---

## Commit Types

| Type | 설명 |
|------|------|
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 변경 |
| `refactor` | 리팩토링 |
| `test` | 테스트 코드 추가/수정 |
| `chore` | 빌드, 설정, 기타 |

## Commit Format

```
<type>: <description>

[optional body]

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## Execution Steps

### 1. 변경사항 분석

```bash
git status
git diff --staged
git diff
git log --oneline -5
```

### 2. Type 결정

| 변경 내용 | 권장 타입 |
|----------|----------|
| 새 기능/액션 추가 | `feat` |
| 버그 수정 | `fix` |
| 문서 변경 (README, docs/) | `docs` |
| 코드 구조 개선 | `refactor` |
| 테스트 코드 | `test` |
| 설정, 스킬, 기타 | `chore` |

> 소스코드 + 문서가 함께 변경되면 소스코드의 type을 따른다. 문서만 변경 시 `docs`.

### 3. 커밋 메시지 생성 규칙

```
- Header 72자 이하
- 한글 또는 영문 (프로젝트 기존 커밋 스타일 따름)
- 끝에 마침표 없음
- Body에 주요 변경 항목 나열 (선택)
```

### 4. 파일 스테이징 및 커밋

자동 생성 파일(`.serena/project.yml` 등)은 제외한다.

```bash
git add <relevant-files>
git commit -m "$(cat <<'EOF'
<type>: <description>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### 5. 검증

```bash
git status
git log --oneline -1
```

---

## Examples

```bash
feat: CLICK_SNAPSHOT_TEXT 퍼지 매칭 액션 추가
fix: CDP 직접 입력에서 특수문자 이스케이프 오류 수정
docs: README 범용 프레임워크 구조로 전면 재작성
refactor: 하드코딩된 자격증명을 환경변수로 분리
test: 시나리오 파서 단위 테스트 추가
chore: requirements.txt websocket-client 추가
```

---

**Related Skills:**
- [create-pr](../create-pr/SKILL.md) - PR 생성
