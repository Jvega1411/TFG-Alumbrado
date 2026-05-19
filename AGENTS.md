# AGENTS.md - TFG-Alumbrado

This is the code and deploy repository for the TVITEC lighting supervision
gateway. Keep it focused on runnable code, deploy scripts, tests, and the small
set of source artifacts needed to validate PLC addresses.

## Session Protocol

If the Obsidian vault repository `TFG-Alumbrado-Vault` is available, start from
its root `AGENTS.md`, then read today's daily note and
`00_Index/Pending Questions.md` before working here.

Do not add planning notes, agent memories, chat logs, raw packet captures, or
research drafts to this repo. Those belong in the vault or in local ignored
files.

## Project

- Purpose: read-only supervision and data capture for industrial lighting.
- PLC: Omron Sysmac CJ2M over FINS/UDP.
- OT node: Raspberry Pi publisher, no database/API in phase 2.
- IT node: Lenovo runs Mosquitto, subscriber, SQLite/API/dashboard.
- UI: FastAPI serves static HTML/CSS/JS from `web/`.

This system is not a control system. It must not modify the PLC or lighting
installation.

## Safety Rules

- No FINS writes, force/set/reset, mode changes, or PLC memory modifications.
- No endpoints or UI controls that can change PLC state.
- Do not read, print, commit, or summarize secrets from `.env`, credentials,
  private keys, connection strings, or real databases.
- Do not run commands against the real PLC, OT network, system services,
  firewall, `/opt`, or production databases without explicit user approval.
- If a value is unknown, mark it pending. Do not invent PLC semantics.

## Sources Of Truth

- `Tabla_ES.html`: PLC variable address and name truth when present.
- `LD_Ilum.pdf`: ladder behavior truth when locally provided; it is ignored and
  should not be committed.
- Curated vault notes and pending questions are project memory.
- Raw smoke JSON, packet captures, databases, and local scans are not project
  memory; summarize findings in the vault instead.

## Repo Shape

Keep these as the main maintained surfaces:

- `acquisition/`: FINS polling and MQTT publishing.
- `subscriber/`: MQTT payload ingestion.
- `fins/`: passive FINS client/frame/diagnostics.
- `model/`: SQLAlchemy models and persistence.
- `schemas/`: API and payload schemas.
- `api/`: read-only FastAPI routes.
- `web/`: dashboard static assets.
- `scripts/node-config/`: deploy and node configuration helpers.
- `tests/`: local verification.
- `alembic/`: migrations.

Avoid adding new top-level folders unless they are part of runtime, deployment,
or tests.

## Development Rules

- Prefer minimal, localized changes.
- Preserve Raspberry Pi and Windows Lenovo compatibility.
- Use structured parsers/APIs instead of ad hoc string handling when practical.
- Keep the dashboard read-only unless the user explicitly asks for authenticated
  write-mode work.
- Update tests when behavior changes.
- Run proportional verification before declaring work complete.

## Cleanup Rules

The following must stay out of git:

- `.claude/`, `.roundtable/`, `.superpowers/`
- `ROUNDTABLE.md`, `agents/`, `tasks/`
- `docs/superpowers/`, `docs/roundtable-design.md`
- `Wiresharks/`, raw packet captures, raw smoke dumps
- runtime databases, caches, virtualenvs, build outputs, secrets

If one of these is needed temporarily, keep it local and ignored.
