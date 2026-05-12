# Spec: Obsidian Vault — Knowledge Base for TFG-Alumbrado

**Date:** 2026-05-12
**Status:** Approved for implementation
**Authors:** Sebas + Claude Code + Codex

---

## Purpose

A shared, persistent knowledge base that survives session boundaries for both Sebas and the AI agents (Claude Code, Codex). It serves three roles simultaneously:

1. **Agent context** — agents read it at session start to situate themselves without re-deriving project state from scratch
2. **Knowledge record** — timestamped decisions, findings, and open questions with a clear resolution trail
3. **Learning resource** — technical concepts explained in plain language for Sebas, with commented code and wikilinks to concept files

---

## Two-Repo Architecture

The vault is a **separate git repository** (`TFG-Alumbrado-vault`) independent of the code repo (`TFG-Alumbrado`).

**Why separate:** Code commits stay clean and focused. The vault's git history shows the evolution of knowledge independently. Graphify indexes both repos and outputs its readable artifacts into the vault.

```
TFG-Alumbrado/          ← code repo (existing)
  fins/
  acquisition/
  config/
  model/ api/ tests/
  docs/superpowers/
  .graphifyignore       ← excludes .env, raw JSONs, DBs, etc. (committed)
  graph.json            ← gitignored; regenerated locally by Graphify
  CLAUDE.md             ← hand-written pointer to vault added by Sebas

TFG-Alumbrado-vault/    ← new repo (this spec)
  AGENTS.md             ← pinned entry point for all agents (hand-written)
  LOCAL_PATHS.md        ← gitignored; machine-specific code repo path
  .gitignore            ← ignores LOCAL_PATHS.md, graph.html
  00_Index/
  10_Daily/
  20_Decisions/
  30_PLC/
  40_Architecture/
  50_AI_Context/
  60_Concepts/
  graph/
    GRAPH_REPORT.md     ← committed after manual Sebas review
    graph.html          ← gitignored; regenerated on demand
```

---

## Vault Structure

### `AGENTS.md` — vault root, pinned entry point

Every agent (Claude Code and Codex) reads this file first, every session, before doing anything else. It contains:

1. The session protocol (read daily note → work → append → commit)
2. The newer-prevails rule and its exceptions
3. The writing contract (What/Why/Where format, concept linking, educational tone)
4. The path to the code repo on disk

### `00_Index/`

| File | Owner | Purpose |
|---|---|---|
| `Project Map.md` | Sebas | Static high-level overview of the project. Rarely changes. |
| `Pending Questions.md` | Agents (updated every session) | Running list of unresolved PENDIENTEs. Agents add and strike through items as they are resolved. |

`Current Truth.md` is deliberately absent — the latest daily note carries that role, keeping one fewer document to maintain.

### `10_Daily/`

One `.md` file per calendar day. Multiple sessions on the same day **append** to the same file — they do not create new files.

Format: see **Daily Note Format** section below.

### `20_Decisions/`

Longer-form decision records for significant architectural or design choices. Created when a decision warrants more context than fits in a daily note entry. Named `YYYY-MM-DD-<slug>.md`.

Examples: `2026-05-12-sqlite-fase2.md`, `2026-05-12-fins-smoke-test.md`

Structure:
```
# Decision: <title>
Date: YYYY-MM-DD
Decided by: Sebas / Claude Code / Codex

## Context
## Decision
## Alternatives considered
## Trade-offs
## Consequences
```

### `30_PLC/`

| File | Purpose |
|---|---|
| `Variables Validated.md` | Memory addresses confirmed against Tabla_ES.html or LD_Ilum.pdf. Each entry shows area, address, variable name, source of confirmation. |
| `Variables Pending.md` | Addresses in use but not yet formally confirmed. Includes smoke test empirical evidence. |
| `Smoke Test Findings.md` | **Only indexed smoke source.** Curated, human-written summary of captures: what was confirmed, anomalies, clock readings, cycle time. References raw files by filename (e.g. `fins_smoke_20260512_075408Z.json`) but does not embed raw JSON. Raw files remain in `data/smoke_fins/` and are never copied into the vault. |

### `40_Architecture/`

Living architecture notes. Agents update these when the architecture evolves.

| File | Purpose |
|---|---|
| `Fase 2 Overview.md` | Two-node architecture: RPi (OT) → MQTT → Lenovo (IT) |
| `MQTT Payload.md` | Payload schema, topic, QoS, change-detection logic |
| `SQLite Schema.md` | Single `bd_alumbrado.db` schema for Fase 2: `ciclo`, `seccion_estado`, `horario_tramo` tables. Does not reference the old BD_Estados/BD_Historizacion split from Fase 1. |
| `API Contract.md` | FastAPI endpoint list with input/output shapes |

### `50_AI_Context/`

| File | Purpose |
|---|---|
| `Claude Context.md` | What works well with Claude Code, quirks, preferred patterns for this project |
| `Codex Context.md` | What works well with Codex, quirks, preferred patterns |
| `Agent Rules.md` | Shared conventions both agents follow (commit format, write style, concept linking) |

### `60_Concepts/`

**Grows organically.** A new file is created the first time a concept appears in a session decision or finding. Written for Sebas — plain language, analogies, commented code examples. Not for agent-to-agent communication.

Each file follows this structure:
```
# <Concept Name>
_First encountered: YYYY-MM-DD_

## What it is
## Why it matters for this project
## Code example (commented for understanding)
## Further reading (optional)
```

Initial files expected to appear early:
- `FINS-Protocol.md`
- `BCD-Encoding.md`
- `Sockets-y-NICs.md`
- `MQTT-Explained.md`
- `SQLAlchemy-Explained.md`

### `graph/`

Graphify output — generated, not hand-edited.

| File | Purpose |
|---|---|
| `GRAPH_REPORT.md` | Human and agent-readable code map. Agents read this at session start for code structure. |
| `graph.html` | Interactive browser visualization. For Sebas to explore relationships visually. |

`graph.json` (raw machine-readable graph) stays in the code repo, not the vault.

---

## Daily Note Format

### File naming
`10_Daily/YYYY-MM-DD.md` — one file per calendar day.

### Session block
Each session (Claude Code or Codex) opens with a header block, then appends its own sections:

```markdown
# 2026-05-12

---
## ── Session 1 · Claude Code · 07:30 UTC
**Context on arrival:** <one line — what state the project was in when this session started>

### Decisions

#### <Decision title>
- **What:** <what changed or was chosen>
- **Why:** <plain-language explanation — written for Sebas>
- **Where:** `<filename> · line <N>` in TFG-Alumbrado (code repo)
- → See [[60_Concepts/<ConceptFile>]] _(if a new concept is introduced)_

### Findings
- <empirical discovery — PLC readings, test results, code inspection>

### Explained
<Short plain-language explanation of one concept that appeared this session.>

```python
# <filename> · <function or context>
# Comment explains WHY, not what — written for Sebas
<code snippet>
```
→ [[60_Concepts/<ConceptFile>]]

### Pending
- <open question or unresolved item — also added to 00_Index/Pending Questions.md>

### Supersedes
- <what older note or assumption this session corrects>

---
## ── Session 2 · Codex · 15:00 UTC
**Context on arrival:** Read session 1 above. <brief state description>

<... same sections appended below ...>
```

---

## AGENTS.md — Full Contract

```markdown
# AGENTS.md — TFG-Alumbrado-vault

## Code repo path
See `LOCAL_PATHS.md` in this vault root (gitignored, machine-specific).
`LOCAL_PATHS.md` contains the absolute path to `TFG-Alumbrado` on this machine.
Sebas creates it on first setup. Agents read it to know where the code lives.
It is never committed — each machine maintains its own copy.

## Session protocol — mandatory, every session

1. **Situate:** Read today's `10_Daily/YYYY-MM-DD.md` fully.
   - If it exists: read all prior sessions to understand current state.
   - If it doesn't exist: create it from the daily note template.
2. **Read:** `00_Index/Pending Questions.md` before starting work.
3. **Read:** `graph/GRAPH_REPORT.md` if you need code structure context.
4. **Work** in the code repo.
5. **Append** your session block to today's daily note when done (even if brief).
6. **Update** `00_Index/Pending Questions.md` — add new items, strike resolved ones.
7. **Commit the vault only if it was modified.** If you only read and made no changes, note "no vault changes this session" in the daily note and skip the commit. Commit message: `git commit -m "session: YYYY-MM-DD <AgentName>"`

## Writing contract

- **Decisions use What / Why / Where.** Where = exact file + line in the code repo.
- **Tone is educational.** Sebas is a student. Explain technical decisions in plain language.
- **Link concepts.** When a technical term appears for the first time in a session, link to `[[60_Concepts/ConceptName]]`. Create the file if it doesn't exist.
- **Code snippets are commented for Sebas**, not for the compiler. Explain the why.
- **Never summarize without explaining.** "Fixed bind" is not enough. Explain what bind is.

## Newer-prevails rule

If two notes contradict each other, the newer date wins.

**Exception — these sources always override any note:**
- `Tabla_ES.html` — PLC variable address ground truth
- `LD_Ilum.pdf` — ladder diagram ground truth
- Smoke test captures in `data/smoke_fins/` — **for observed values only** (e.g. "W25=1 was read"). Semantic interpretation of what a value means (e.g. "W25=1 means entfot1 is active") still requires confirmation against LD_Ilum.pdf or an explicit Sebas decision.
- An explicit decision by Sebas (marked "Sebas decision" in the note)

## What NOT to write to the vault

- `.env` content, credentials, passwords, connection strings
- Raw smoke JSON files (those stay in `data/smoke_fins/` in the code repo)
- Generated files (`__pycache__`, `.db`, `.venv`)
```

---

## Graphify Integration

**What Graphify does:** Combines Tree-sitter static analysis (code structure) with LLM semantic extraction (intent and relationships) to produce a knowledge graph of the entire codebase and documentation.

**What it indexes:**
- All Python source files in `TFG-Alumbrado/`
- `docs/superpowers/plans/` and `docs/superpowers/specs/`
- `Tabla_ES.html`
- Vault notes in `TFG-Alumbrado-vault/`
- `30_PLC/Smoke Test Findings.md` (curated only — see above)

**What it does NOT index — enforced via `.graphifyignore`:**

A `.graphifyignore` file must be created and committed **before the first Graphify run**. It must include at minimum:

```
.env
.venv/
.pytest_cache/
__pycache__/
.superpowers/
data/smoke_fins/*.json
*.db
*.sqlite
graph.json
graphify-out/
LOCAL_PATHS.md
```

**Output location and commit policy:**
- `TFG-Alumbrado-vault/graph/GRAPH_REPORT.md` — committed to vault **only after manual review by Sebas**
- `TFG-Alumbrado-vault/graph/graph.html` — regenerated on demand, not committed (too large, always reproducible)
- `TFG-Alumbrado/graph.json` — **gitignored in the code repo**, never committed; regenerated locally when needed

**Graphify must not modify `CLAUDE.md` or `AGENTS.md`.**
These files are hand-written agent contracts. Any Graphify feature that auto-generates or overwrites instruction files is disabled. If Graphify produces suggested agent context, it is written to a separate `graph/AGENT_SUGGESTIONS.md` that Sebas reviews and manually integrates — it never auto-updates the contracts.

A short hand-written pointer to the vault is added manually to `TFG-Alumbrado/CLAUDE.md` by Sebas during setup. Graphify does not touch this file.

**Run frequency:** On demand. Sebas runs Graphify when the codebase or vault has changed significantly. Not automated in CI.

---

## Conflict Resolution Rules

| Situation | Rule |
|---|---|
| Two notes on different dates contradict | Newer date wins |
| A note contradicts Tabla_ES.html | Tabla_ES.html wins |
| A note contradicts LD_Ilum.pdf | LD_Ilum.pdf wins |
| A note contradicts a smoke capture | Smoke capture wins for **observed values** (what was read). Semantic meaning (what the value signifies) still requires LD_Ilum.pdf or Sebas confirmation. |
| A note contradicts a Sebas decision | Sebas decision wins |
| Two agents write conflicting content same day | Sebas resolves manually; later session notes the resolution |

---

## Setup Steps (high level — implementation plan will detail these)

1. Create `TFG-Alumbrado-vault` as a new git repo with `.gitignore` (ignores `LOCAL_PATHS.md`, `graph.html`)
2. Create the folder structure and hand-write seed files: `AGENTS.md`, `00_Index/Project Map.md`, `00_Index/Pending Questions.md`, template daily note for today
3. Create `LOCAL_PATHS.md` locally (not committed) with the absolute path to `TFG-Alumbrado`
4. Install Graphify; create and commit `.graphifyignore` in the code repo **before first run**
5. Add a short hand-written vault pointer to `TFG-Alumbrado/CLAUDE.md` manually — Graphify does not touch this file
6. Run Graphify; review `GRAPH_REPORT.md` output; commit to vault only if content is useful and accurate
7. Seed initial vault content: `30_PLC/Smoke Test Findings.md` (curated from smoke captures), `40_Architecture/Fase 2 Overview.md` (from existing spec)

---

## Out of Scope

- Obsidian plugin configuration (plugins, themes, hotkeys) — Sebas configures these manually
- Automated Graphify runs via CI — on-demand only for now
- Syncing the vault to cloud (Obsidian Sync, GitHub Pages) — future consideration
- Any write access to the PLC or OT network
