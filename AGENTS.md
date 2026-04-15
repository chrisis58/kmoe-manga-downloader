# AGENT.md — kmoe-manga-downloader

## Project Overview

`kmdr` (Kmoe Manga Downloader) is a Python CLI application for downloading manga from the [Kmoe](https://kxx.moe/) website. It provides login, download (with multi-part/resume/failover), credential pool management, and persistent configuration — all through a rich terminal interface.

- **Entry point**: `kmdr.main:entry_point` (registered as `kmdr` CLI command)
- **Python**: ≥ 3.9
- **Package layout**: `src/kmdr/` (src layout)
- **Build**: Poetry + `poetry-dynamic-versioning` (PEP 517 backend)
- **Versioning**: Dynamic from Git tags via `poetry-dynamic-versioning`, placeholder in `src/kmdr/_version.py`

## Architecture

### Core (`src/kmdr/core/`)

The core layer defines **abstract base classes**, a **Registry-based plugin system**, data models, and shared infrastructure.

#### Registry Pattern (`registry.py`)

The central design pattern. `Registry[T]` is a generic container that maps command-line arguments (`argparse.Namespace`) to module implementations via predicate matching.

```
Registry.register(hasattrs, containattrs, hasvalues, predicate, order)
Registry.get(args) → T  # resolves and instantiates the matching implementation
```

Matching logic: `{predicate} OR {hasvalues} AND ({hasattrs} OR {containattrs})`. Registrations are sorted by `order` (lower = higher priority).

Eight global registries are defined in `bases.py`:

| Registry           | Base Class       | Purpose                    |
|--------------------|------------------|----------------------------|
| `SESSION_MANAGER`  | `SessionManager` | HTTP session lifecycle     |
| `AUTHENTICATOR`    | `Authenticator`  | Login / cookie auth        |
| `CATALOGERS`       | `Cataloger`      | Fetch book list collections|
| `LISTERS`          | `Lister`         | Fetch book & volume info   |
| `PICKERS`          | `Picker`         | Filter/select volumes      |
| `DOWNLOADER`       | `Downloader`     | Download volumes           |
| `CONFIGURER`       | `Configurer`     | Config operations          |
| `POOL_MANAGER`     | `PoolManager`    | Credential pool management |

#### Mixin Contexts (`context.py`)

Base classes use cooperative multiple inheritance with context mixins:

- `TerminalContext` — provides `_console` (Rich Console) and `_progress` (Progress bar)
- `SessionContext` — provides `_session` and `_base_url` via `ContextVar`
- `ConfigContext` — provides `_configurer` (singleton JSON config manager)
- `CredentialPoolContext` — provides `_pool` (lazy-loaded `CredentialPool`)

#### Data Models (`structure.py`)

- `BookInfo` — immutable book metadata (id, name, author, url, status)
- `VolInfo` — immutable volume metadata (id, name, type, pages, size)
- `Credential` — mutable user credential (username, cookies, quotas, status, order)
- `QuotaInfo` — user/VIP quota tracking with unsynced usage
- `Config` — persistent config (options, cookie, base_url, cred_pool)
- `VolumeType` — enum: `VOLUME`, `EXTRA`, `SERIALIZED`

#### Key Modules

- **`defaults.py`** — `argparse` definitions, `Configurer` singleton (reads/writes `~/.kmdr` JSON), argument merging for persistent options
- **`session.py`** — `KmdrSessionManager`: creates `aiohttp.ClientSession`, probes mirror URLs with priority sorting
- **`pool.py`** — `CredentialPool` (tiered round-robin scheduling with sticky-preferred cred) and `PooledCredential` (quota reservation with transactional commit/rollback)
- **`utils.py`** — `async_retry` decorator (exponential backoff, redirect handling), `PrioritySorter`, `SharedAwaitable` (for concurrent auth+catalog), callback construction, UA rotation
- **`console.py`** — `info()` / `debug()` / `log()` output functions, adapts between interactive (`print`) and non-interactive (`log`) modes; **Tool Call Mode**: `emit()` for final result, `emit_progress()` for real-time NDJSON progress
- **`encoder.py`** — `KmdrJSONEncoder` (standard JSON encoder for dataclasses) and `SafeJSONEncoder` (auto-desensitizes fields marked `sensitive=True`)
- **`error.py`** — Exception hierarchy rooted at `KmdrError(RuntimeError)` with two-digit status codes; includes solution suggestions
- **`patch.py`** — Monkey-patches `Console.status()` to support nested/stacked status contexts in async scenarios

#### Error Status Codes (`error.py`)

Two-digit status codes categorized by domain: 0 (success), 1x (init/args), 2x (auth/cred), 3x (redirect), 4x (input), 5x (server/network). See `error.py` for details.

#### Tool Call Mode

When invoked with `--mode toolcall`, kmdr outputs structured NDJSON for AI agent consumption:

- **Output format**: Each line is a JSON object; final line is `{"type": "result", "code": N, "msg": "...", "data": {...}}`
- **Progress updates**: Download commands emit `{"type": "progress", ...}` lines during execution
- **Desensitization**: `SafeJSONEncoder` automatically replaces sensitive fields (cookies, passwords) with `"***SENSITIVE***"`
- **Fast Auth**: `--fast-auth` flag skips network validation, uses local credential pool directly via `LocalPoolAuthenticator`

### Modules (`src/kmdr/module/`)

Concrete implementations registered to the core registries. Each subdirectory is a feature module.

#### `cataloger/`
Provides book list fetching. `SearchCataloger` for keyword search, `FollowedCataloger` for followed books. Contains HTML parsing utilities.

#### `authenticator/`
Handles authentication. `LoginAuthenticator` for username/password login, `CookieAuthenticator` for cookie-based auth, `LocalPoolAuthenticator` for fast auth mode.

#### `lister/`
Fetches book info and volume list. `BookUrlLister` from direct URL, `CatalogGuidedLister` via interactive selection.

#### `picker/`
Filters/selects volumes. `ArgsFilterPicker` via CLI args, `DefaultVolPicker` via interactive selection.

#### `downloader/`
Downloads volumes. `ReferViaDownloader` (API-based), `DirectDownloader` (URL construction), `FailoverDownloader` (credential pool wrapper). Contains download utilities and progress tracking.

#### `configurer/`
Manages persistent config operations: set, list, clear, unset options and base URL updates.

#### `pool/`
Manages credential pool: add, remove, switch, update, list credentials.

## Command Flow

```
entry_point() → parse_args → main(args)
  ├─ "version"  → print version
  ├─ "login"    → SESSION_MANAGER.get() → AUTHENTICATOR.get() → authenticate
  ├─ "status"   → SESSION_MANAGER.get() → AUTHENTICATOR.get() → show quota
  ├─ "config"   → CONFIGURER.get() → operate
  ├─ "search"   → SESSION_MANAGER.get() → AUTHENTICATOR + CATALOGERS → return BookInfo list
  ├─ "download" → SESSION_MANAGER.get() → [AUTHENTICATOR + LISTERS] → PICKERS → DOWNLOADER
  └─ "pool"     → POOL_MANAGER.get() → operate
```

## Skill Definition (`skill/kmdr/`)

The `skill/kmdr/` directory contains a Agent skill definition for AI agent integration:

- **`SKILL.md`** — Skill metadata and usage guide for AI agents to invoke kmdr
- **`references/commands.md`** — Detailed command documentation with parameters and output examples
- **`references/output-format.md`** — NDJSON output format specification for toolcall mode
- **`references/error-codes.md`** — Complete error status code reference with recovery strategies
- **`assets/examples/`** — Example JSON outputs for each command type

## Development

### Setup

```bash
poetry install --with dev
```

### Run Tests

```bash
poetry run pytest
```

### Lint & Format

```bash
poetry run ruff check src/
poetry run ruff format src/
```

### Build

```bash
poetry build
# Or via standard tooling:
pip install build && python -m build
```

### Ruff Config

- Target: Python 3.9
- Line length: 150
- Rules: E, W, F, I, UP, B
- Quote style: double

## Configuration

User config is stored at `~/.kmdr` as JSON, managed by the `Configurer` singleton. It persists:
- Login cookies
- Download options (dest, proxy, retry, callback, num_workers, format)
- Base URL (mirror)
- Credential pool

## Key Conventions

1. **Chinese comments and user-facing strings** — the project targets Chinese-speaking users; all UI text, error messages, and docstrings are in Chinese
2. **Registry-based dispatch** — new modules should be registered via `@REGISTRY.register()` decorator, not by modifying `main.py`
3. **Cooperative inheritance** — base classes use `*args, **kwargs` passthrough and `super().__init__()` for MRO-compatible initialization
4. **Async-first** — all I/O operations use `asyncio` + `aiohttp` + `aiofiles`; sync operations are delegated via `asyncio.to_thread()`
5. **`ContextVar` for session state** — `session_var` and `base_url_var` allow implicit session sharing across the call stack
6. **Quota management** — `PooledCredential` uses a reservation system (`reserve` → `commit`/`rollback`) to safely handle concurrent downloads across multiple credentials
7. **Tool Call Mode output** — when `--mode toolcall` is set, use `emit()` for final results and `emit_progress()` for real-time progress; outputs NDJSON format
8. **Sensitive data desensitization** — mark sensitive fields with `metadata={"sensitive": True}` in dataclass definitions; `SafeJSONEncoder` handles output
9. **Explain mode** — `--explain` flag on download command outputs estimated quota consumption and download plan without executing actual downloads
