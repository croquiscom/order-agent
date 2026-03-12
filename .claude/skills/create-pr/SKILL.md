---
name: create-pr
description: "GitHub PR 자동 생성. Use when: PR 만들어줘, 풀리퀘, PR 생성, github 반영."
---

# Create Pull Request

GitHub에 PR을 생성하고 설명을 자동 생성한다.

**When to Use:** "PR 만들어줘", "풀리퀘", "PR 생성", "github 반영"
**Not for:** 커밋 (-> `commit`)

---

## Branch Naming Convention

| Type | Branch Pattern | Example |
|------|---------------|---------|
| `feat` | `feat/<description>` | `feat/snapshot-text-action` |
| `fix` | `fix/<description>` | `fix/cdp-special-char` |
| `docs` | `docs/<description>` | `docs/readme-rewrite` |
| `refactor` | `refactor/<description>` | `refactor/env-credentials` |
| `test` | `test/<description>` | `test/parser-unit-tests` |
| `chore` | `chore/<description>` | `chore/deps-update` |

---

## Execution Steps

### 1. 현재 상태 확인

```bash
git status
git diff --staged
git diff
git branch --show-current
git log main..HEAD --oneline
git diff main...HEAD --stat
```

- 미커밋 변경이 있으면 `/commit` 스킬을 먼저 안내한다.
- 현재 브랜치가 `main`이면 새 브랜치 생성을 안내한다.

### 2. 변경사항 분석

```bash
git diff main...HEAD
git log main..HEAD --oneline
```

전체 커밋 히스토리를 분석하여 PR 제목과 설명을 결정한다.

### 3. PR 제목 결정

```
<type>: <description>
```

- 72자 이하
- Conventional Commit 형식
- 커밋이 여러 개면 전체 변경을 아우르는 제목

### 4. PR 설명 생성

```markdown
## Summary
- 변경 항목 1
- 변경 항목 2
- 변경 항목 3

## Test plan
- [ ] 테스트 항목 1
- [ ] 테스트 항목 2
```

### 5. Push 및 PR 생성

```bash
# remote에 push (필요한 경우)
git push -u origin <branch-name>

# PR 생성
gh pr create --title "<title>" --assignee @me --body "$(cat <<'EOF'
## Summary
- ...

## Test plan
- [ ] ...
EOF
)"
```

### 6. 검증

```bash
gh pr view --json url,title,body
```

PR URL을 사용자에게 출력한다.

---

## Checklist

```
- [ ] 미커밋 변경 없음
- [ ] 브랜치 컨벤션 준수
- [ ] remote push 완료
- [ ] PR 제목 Conventional Commit 형식
- [ ] PR 설명에 Summary + Test plan 포함
- [ ] PR URL 출력
```

---

**Related Skills:**
- [commit](../commit/SKILL.md) - 커밋 생성
