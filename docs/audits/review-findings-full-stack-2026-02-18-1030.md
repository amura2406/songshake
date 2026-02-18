# Code Audit: Full Stack (Web, Backend API, CLI)
Date: 2026-02-18
Reviewer: AI Agent (fresh context)

## Summary
- **Files reviewed:** 14 (7 Python backend + 7 JS/JSX frontend)
- **Issues found:** 35 (6 critical, 14 major, 12 minor, 3 nit)
- **Test coverage:** 0% — zero test files exist anywhere in the project

## Verification Results
- **ESLint:** FAIL (18 errors, 2 warnings)
- **Vite Build:** PASS
- **Python Compile:** PASS (all 7 files)
- **Tests:** N/A — no test runner configured, no tests exist

---

## Critical Issues

Issues that must be fixed before deployment.

- [ ] **[SEC]** CORS allows all origins with credentials — `allow_origins=["*"]` combined with `allow_credentials=True` is a dangerous combination. Browsers block `Access-Control-Allow-Credentials` with wildcard origin, but this signals intent to relax security. Must restrict to specific origins. — [api.py:23-29](file:///Users/anggar/Code/song-shake/src/song_shake/api.py#L23-L29)

- [ ] **[SEC]** Hardcoded redirect URI uses `localhost:8000` — The Google OAuth callback is hardcoded to `http://localhost:8000/auth/google/callback` with plain HTTP. If deployed to production, this breaks OAuth and exposes tokens over unencrypted transport. Should be configurable via environment variable. — [api.py:211](file:///Users/anggar/Code/song-shake/src/song_shake/api.py#L211), [api.py:230](file:///Users/anggar/Code/song-shake/src/song_shake/api.py#L230), [api.py:242](file:///Users/anggar/Code/song-shake/src/song_shake/api.py#L242)

- [ ] **[SEC]** Frontend hardcodes `localhost:8000` for auth redirect — `Login.jsx` line 47 hardcodes `window.location.href = 'http://localhost:8000/auth/google/login'`, bypassing the Vite proxy and exposing the backend directly. Should use the relative `/auth/google/login` path. — [Login.jsx:47](file:///Users/anggar/Code/song-shake/web/src/components/Login.jsx#L47)

- [ ] **[SEC]** OAuth tokens stored to `oauth.json` as plain file in working directory — Tokens (including `access_token`, `refresh_token`, `client_secret`) are written directly to an unencrypted file in the project root. Any process with file-system access can read them. The file path is hardcoded with no permission restrictions. — [auth.py:10](file:///Users/anggar/Code/song-shake/src/song_shake/auth.py#L10), [api.py:88](file:///Users/anggar/Code/song-shake/src/song_shake/api.py#L88), [api.py:252](file:///Users/anggar/Code/song-shake/src/song_shake/api.py#L252), [api.py:316](file:///Users/anggar/Code/song-shake/src/song_shake/api.py#L316)

- [ ] **[SEC]** Error messages expose internal details to clients — Multiple endpoints return `str(e)` directly in HTTPException details, potentially leaking stack traces, file paths, and internal state to callers. Examples: `api.py:84`, `api.py:196`, `api.py:257`, `api.py:330`, `api.py:406`. — [api.py:84](file:///Users/anggar/Code/song-shake/src/song_shake/api.py#L84)

- [ ] **[SEC]** Client stores OAuth credentials in `localStorage` — `Login.jsx` stores `google_client_id` and `google_client_secret` in `localStorage`, which is accessible to any JavaScript on the page (XSS attack vector). — [Login.jsx:12-13](file:///Users/anggar/Code/song-shake/web/src/components/Login.jsx#L12-L13)

---

## Major Issues

Issues that should be fixed in the near term.

- [x] **[TEST]** Zero test files exist — ✅ FIXED: Added `test_storage.py` (14 tests) and `test_enrichment.py` (4 tests) with pytest infrastructure. 18/18 passing.

- [x] **[TEST]** No I/O abstraction — ✅ FIXED: Created `protocols.py` with 4 Protocol classes (`StoragePort`, `AudioDownloader`, `AudioEnricher`, `PlaylistFetcher`).

- [x] **[OBS]** No structured logging — ✅ FIXED: Created `logging_config.py` with `structlog` (JSON prod, colored dev). Replaced all 12 `print()` debug/error calls with structured logger calls across `api.py`, `auth.py`, `enrichment.py`.

- [x] **[ERR]** Bare `except:` with `pass` swallows errors silently — ✅ FIXED: Changed to specific exception types (`json.JSONDecodeError`, `(ValueError, SyntaxError)`, `Exception`) with logging.

- [x] **[ERR]** Unreachable code in `get_current_user` — ✅ FIXED: Removed unreachable return statement.

- [x] **[ARCH]** `api.py` is a 551-line monolith — ✅ FIXED: Split into `routes_auth.py`, `routes_playlists.py`, `routes_enrichment.py`, `routes_songs.py`. `api.py` reduced from 561 → 38 lines (thin app shell).

- [x] **[ARCH]** In-memory task state (`enrichment_tasks` dict) is lost on restart — ✅ FIXED: Task state now persisted to TinyDB via `save_task_state()`/`get_task_state()`. Status endpoint falls back to DB when task isn't in memory.

- [x] **[ARCH]** `OAuthCredentials` used in `api.py` but never imported — ✅ FIXED: Added missing import (now in `routes_auth.py`).

- [x] **[ARCH]** Duplicate import — ✅ FIXED: Removed duplicate `urlencode` import.

- [x] **[ARCH]** Project structure doesn't follow feature-based organization — ✅ FIXED: Backend reorganized into `features/auth/`, `features/enrichment/`, `features/songs/`, and `platform/` (logging, protocols). Frontend reorganized into `features/auth/`, `features/enrichment/`, `features/songs/`, and `components/layout/`. — [src/song_shake/](file:///Users/anggar/Code/song-shake/src/song_shake/), [web/src/](file:///Users/anggar/Code/song-shake/web/src/)

- [x] **[ERR]** No input validation on API endpoints — ✅ FIXED: Added `Query(ge=0)`, `Query(ge=1, le=200)`, `Query(ge=1, le=300)` constraints on `/songs` parameters.

- [x] **[ERR]** `enrichment.py:155` bare `except:` hides JSON parse failures — ✅ FIXED: Changed to `except json.JSONDecodeError` with `logger.warning()` call.

- [x] **[ERR]** No timeout on external HTTP requests — ✅ FIXED: Added `timeout=10` to all 5 `requests.get()`/`requests.post()` calls across `auth.py` and `routes_auth.py`.

---

## Minor Issues

Style, naming, or minor improvements.

- [ ] **[PAT]** ESLint reports 18 errors across frontend — Unused imports (`motion`, `useRef`, `useSearchParams`, `getEnrichmentStatus`, `getEnrichmentStreamUrl`), unused state variables (`processing`, `logs`, `logContainerRef`), unused function (`handleLogout` in Dashboard, `formatDuration` in Results), and missing React Hook dependencies. — [Dashboard.jsx](file:///Users/anggar/Code/song-shake/web/src/components/Dashboard.jsx), [Enrichment.jsx](file:///Users/anggar/Code/song-shake/web/src/components/Enrichment.jsx), [Results.jsx](file:///Users/anggar/Code/song-shake/web/src/components/Results.jsx), [Login.jsx](file:///Users/anggar/Code/song-shake/web/src/components/Login.jsx), [Layout.jsx](file:///Users/anggar/Code/song-shake/web/src/components/Layout.jsx)

- [ ] **[PAT]** `show` command in CLI has business logic inline — `main.py:27-94` contains 67 lines of filtering, formatting, and display logic directly in the command handler. Should extract filtering to a pure function and keep the handler thin. — [main.py:27-94](file:///Users/anggar/Code/song-shake/src/song_shake/main.py#L27-L94)

- [ ] **[PAT]** Mixed `print` and `console.print` for output — Backend mixes `print()` (stdlib) and `console.print()` (Rich) inconsistently. Should standardize on one. — throughout Python files

- [ ] **[PAT]** `storage.get_all_tracks` loads entire songs table into memory — Line 91 `all_songs = songs_table.all()` fetches every song, then filters in Python. For large databases, this is inefficient. — [storage.py:91](file:///Users/anggar/Code/song-shake/src/song_shake/storage.py#L91)

- [ ] **[PAT]** `auth.py:setup_auth` has dead code paths — Lines 161-196 contain multiple parsing attempts (raw headers → JSON → ast.literal_eval → YTMusic.setup) where earlier results are overwritten by later ones. The logic is confusing and contains unreachable branches. — [auth.py:159-196](file:///Users/anggar/Code/song-shake/src/song_shake/auth.py#L159-L196)

- [ ] **[PAT]** `Results.jsx` is 566 lines — This single component handles song listing, filtering, pagination, tag selection, BPM range filtering, YouTube player, playback controls, and seek. Should be broken into smaller sub-components. — [Results.jsx](file:///Users/anggar/Code/song-shake/web/src/components/Results.jsx)

- [ ] **[PAT]** Multiple `load_dotenv()` calls scattered across files — `load_dotenv()` is called in `main.py:8`, `api.py:200`, `api.py:206`, `api.py:227`, `api.py:262`, `api.py:279`, `api.py:446`, `auth.py:21`, and `enrichment.py:209`. Should be called once at application startup. — throughout Python files

- [ ] **[PAT]** `api.js` mixes `axios` and raw `fetch` — Some API calls use the configured `axios` instance (with interceptors), while `initGoogleAuth`, `pollGoogleAuth`, and `getEnrichmentStatus` use raw `fetch()`, bypassing the 401 interceptor and error handling. — [api.js:64-93](file:///Users/anggar/Code/song-shake/web/src/api.js#L64-L93)

- [ ] **[PAT]** Frontend `Dashboard.jsx` polls every 5 seconds unconditionally — `loadData` fetches playlists + user info on a 5-second interval regardless of whether any enrichment is running. This is wasteful when idle. — [Dashboard.jsx:34-38](file:///Users/anggar/Code/song-shake/web/src/components/Dashboard.jsx#L34-L38)

- [ ] **[PAT]** `Layout.jsx` polls tags every 5 seconds — Tags rarely change; polling every 5s is excessive. Should use event-driven updates or much longer intervals. — [Layout.jsx:34](file:///Users/anggar/Code/song-shake/web/src/components/Layout.jsx#L34)

- [ ] **[PAT]** `PrivateRoute` makes auth check on every navigation — Each route change triggers a new `GET /auth/status` call. Should cache the auth state in a context provider and share across routes. — [App.jsx:10-26](file:///Users/anggar/Code/song-shake/web/src/App.jsx#L10-L26)

- [ ] **[PAT]** `get_current_user` checks auth by file existence, not token validation — `api.py:94` checks `os.path.exists("oauth.json")` instead of validating the token. A corrupt or expired token file will still pass the existence check. — [api.py:94](file:///Users/anggar/Code/song-shake/src/song_shake/api.py#L94)

---

## Nit

- [ ] `api.py:404` imports `traceback` inside an exception handler — Should be a top-level import. — [api.py:404](file:///Users/anggar/Code/song-shake/src/song_shake/api.py#L404)

- [ ] `enrichment.py:134` re-imports `json` and `re` inside a function — Both are already available at module level (`json`) or unused (`re`). — [enrichment.py:134-135](file:///Users/anggar/Code/song-shake/src/song_shake/enrichment.py#L134-L135)

- [ ] No docstrings on any frontend functions or React components — Makes it harder for new contributors to understand component responsibilities. — entire frontend

---

## Rules Applied
- [rule-priority.md](file:///Users/anggar/Code/song-shake/.agent/rules/rule-priority.md) — Severity classification
- [security-principles.md](file:///Users/anggar/Code/song-shake/.agent/rules/security-principles.md) — OWASP, auth, input validation
- [security-mandate.md](file:///Users/anggar/Code/song-shake/.agent/rules/security-mandate.md) — Defense in depth
- [error-handling-principles.md](file:///Users/anggar/Code/song-shake/.agent/rules/error-handling-principles.md) — No silent failures, context
- [testing-strategy.md](file:///Users/anggar/Code/song-shake/.agent/rules/testing-strategy.md) — Test pyramid, >85% coverage
- [architectural-pattern.md](file:///Users/anggar/Code/song-shake/.agent/rules/architectural-pattern.md) — I/O isolation, pure logic, DI
- [logging-and-observability-mandate.md](file:///Users/anggar/Code/song-shake/.agent/rules/logging-and-observability-mandate.md) — Structured logging
- [code-organization-principles.md](file:///Users/anggar/Code/song-shake/.agent/rules/code-organization-principles.md) — Module boundaries, SRP
- [project-structure.md](file:///Users/anggar/Code/song-shake/.agent/rules/project-structure.md) — Feature-based org
- [rugged-software-constitution.md](file:///Users/anggar/Code/song-shake/.agent/rules/rugged-software-constitution.md) — Defensibility, fail securely

---

## Recommended Fix Priority

| Priority | Type | Workflow | Count |
|----------|------|----------|-------|
| **P0** | Security fixes (CORS, hardcoded URLs, error leaks, token storage) | `/quick-fix` per issue | 6 |
| **P1** | Testability + Tests (add interfaces, DI, write tests) | `/orchestrator` (new feature) | 2 |
| **P2** | Observability (structured logging) | `/orchestrator` (new feature) | 1 |
| **P3** | Architecture (split api.py, feature-based structure) | `/refactor` | 4 |
| **P4** | Error handling + input validation | `/quick-fix` per issue | 5 |
| **P5** | Code quality (ESLint fixes, dead code, polling) | `/quick-fix` batch | 15 |
