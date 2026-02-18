---
description: Git commit with conventional format
---

# Ship: Commit

## Purpose
Bump version, update README, and commit completed work with proper conventional commit format.

> **Note:** For detailed conventions (branch naming, commit types, PR size, merge strategy), 
> see `git-workflow-principles.md` in `.agent/rules/`.

## Prerequisites
- All verification checks pass
- Code is ready for review/merge

## Steps

### 1. Bump Version

Unless the user specifies a different version bump (major, patch, or exact version), **bump the minor version**.

**Locate the version source of truth:**
- **Python:** `pyproject.toml` → `[project] version = "x.y.z"`
- **TypeScript/JS:** `version.ts` or `package.json` → `"version": "x.y.z"`

**Check for duplicated version references:**
```bash
# Search for the current version string across the codebase
grep -rn "<current_version>" --include="*.py" --include="*.ts" --include="*.js" --include="*.toml" --include="*.json" --include="*.md" .
```

If the version is referenced anywhere outside the single source of truth (e.g. hardcoded in code, duplicated in config files), update **all** references to the new version. The goal is a single source of truth, but if duplication exists, keep them in sync.

**Bump example (minor):**
```
0.3.1 → 0.4.0
1.2.5 → 1.3.0
```

### 2. Update README

Review `README.md` and update any sections affected by the current changes:
- **Features list** — add/update if new features were implemented
- **Setup/installation instructions** — update if dependencies or setup steps changed
- **Usage examples** — update if CLI commands, API endpoints, or workflows changed
- **Architecture/structure docs** — update if project structure changed
- **Version references** — update if version is mentioned in README

> Only touch sections that are actually affected. Don't rewrite the entire README.

### 3. Review Changes
```bash
git status
git diff --staged
```

### 4. Stage Changes
```bash
# Stage all changes
git add .

# Or stage selectively (adjust path per project-structure.md)
git add apps/backend/internal/features/task/
```

### 5. Commit with Conventional Format

Follow the format from `git-workflow-principles.md`:

```bash
git commit -m "<type>(<scope>): <description>"
```

**Examples:**
```bash
git commit -m "feat(task): add CRUD API endpoints"
git commit -m "fix(auth): correct token expiry validation"
git commit -m "refactor(storage): extract interface for storage layer"
git commit -m "test(task): add integration tests for storage adapter"
```

### 6. Update task.md
Mark completed items as `[x]` in the task checklist.

## Completion Criteria
- [ ] Version bumped (minor unless user specified otherwise)
- [ ] All version references in sync
- [ ] README updated with relevant changes
- [ ] Changes committed with proper format
- [ ] task.md updated to reflect completion
