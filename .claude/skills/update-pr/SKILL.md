---
name: update-pr
description: "기존 PR 설명을 최신 변경사항으로 업데이트. Use when: PR 업데이트, update PR, PR 수정, PR body 업데이트."
---

# Update Pull Request

기존 PR의 제목과 설명을 최신 변경사항으로 업데이트한다.

**When to Use:** "PR 업데이트", "update PR", "PR 설명 수정", "PR body 업데이트"
**Not for:** 새 PR 생성 (-> `create-pr`), 커밋 (-> `commit`)

---

## Execution Steps

### 1. 기존 PR 확인

```bash
gh pr view --json number,title,body,url
```

PR이 없으면 `create-pr` 스킬 사용을 안내한다.

### 2. 최신 변경사항 분석

```bash
git diff main...HEAD --stat
git diff main...HEAD
git log main..HEAD --oneline
```

PR 생성 이후 추가된 변경사항을 분석한다.

### 3. 제목 업데이트

PR 제목은 전체 커밋 범위를 반영하도록 업데이트한다.
Conventional Commit 형식 유지:

```
<type>: <description>
```

**규칙:**
- 커밋이 1개면 해당 커밋 메시지를 제목으로 사용
- 커밋이 2개 이상이면 전체 변경을 아우르는 요약 제목 생성
- 기존 제목과 동일하면 업데이트 생략

### 4. 설명 업데이트 전략

- **Incremental**: 기존 정보 유지하며 새 정보 추가
- **Context Preservation**: 원래 비즈니스 맥락 유지
- **Change Highlighting**: 업데이트된 내용 명확히 표시

### 5. 적용

```bash
# 제목 업데이트 (변경 시)
gh pr edit --title "<updated-title>"

# 설명 업데이트
gh pr edit --body "$(cat <<'EOF'
## Summary
- 업데이트된 요약

## Test plan
- [ ] 테스트 항목

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### 6. 검증 및 출력

```bash
gh pr view --json url,title,body
```

업데이트된 PR URL을 출력한다.

---

## Checklist

```
- [ ] 현재 브랜치에 PR 존재 확인
- [ ] 전체 커밋 분석 (main..HEAD)
- [ ] 제목이 전체 변경 범위 반영
- [ ] 설명에 최신 변경사항 포함
- [ ] PR URL 출력
```

---

**Related Skills:**
- [create-pr](../create-pr/SKILL.md) - 새 PR 생성
- [commit](../commit/SKILL.md) - 커밋 생성
