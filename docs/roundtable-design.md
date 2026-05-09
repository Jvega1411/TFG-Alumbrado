# Round Table — Design Doc
*Created: 2026-05-09 | Updated: 2026-05-10 | Status: Draft — git connected*

---

## Concept

A terminal-based group chat where Claude Code and OpenAI Codex CLI collaborate on development tasks. The human acts as chair, the agents discuss, propose, review, and reach consensus. Everything is logged to git.

---

## User Context & Constraints

- **Claude Code:** Pro subscription ($20/month) — uses `claude` CLI, not direct API key
- **Codex:** OpenAI Codex CLI (`github.com/openai/codex`) — Pro plan ($20/month)
- **Both CLIs are already running and authenticated** in separate terminals
- **No unlimited usage** — token efficiency is a hard constraint; every design decision must account for it
- **Git repo:** `git@github.com:Jvega1411/TFG-Alumbrado.git`
- **Local path:** `/Users/juansebastian/alumbrado-gateway-receival/TFG-Alumbrado/`
- **SSH auth:** `~/.ssh/id_ed25519_github` — connected and verified

---

## Project Context — TFG-Alumbrado

The round table will work on this codebase:

| Field | Detail |
|---|---|
| **Purpose** | Read-only supervision and data logging for industrial lighting at TVITEC |
| **Hardware** | Omron Sysmac CJ2M CPU32 PLC, FINS/UDP port 9600, IP 192.168.250.1 |
| **Installation** | 1104 luminaires, 172 segments, 112 sections |
| **Stack** | Python 3.x, SQLAlchemy 2.0, Alembic, SQL Server |
| **Databases** | `BD_Estados` (state), `BD_Historizacion` (history) |
| **Dev path** | `/home/master/dev/alumbrado-gateway` (on RPi) |
| **Prod path** | `/opt/alumbrado-gateway` (hands-off) |
| **Service user** | `gwsvc` |

**Architecture layers:**
```
fins/        — FINS/UDP communication
model/       — SQLAlchemy models
schemas/     — validation & serialization
api/         — REST endpoints (read/diagnostic only)
acquisition/ — data acquisition loop
config/      — configuration
main.py      — entry point
```

**Hard constraints agents must respect:**
- Strictly read-only — no FINS writes, no PLC control, no force/set/reset
- No touching `/opt`, systemd, `.env`, real SQL DBs, or OT network without explicit authorization
- No secrets in output or logs
- Validate all PLC variables against `Tabla_ES.pdf` and `LD_Ilum.pdf` — never assume or invent
- Minimum necessary changes — YAGNI, no unsolicited refactors
- RPi compatibility required

---

## Collaboration Model

A hybrid of three dynamics:

| Dynamic | Description |
|---|---|
| **Divide & conquer** | Tasks split by agent strengths (e.g., Claude designs, Codex implements) |
| **Reviewer & author** | One agent writes, the other critiques in the same chat thread |
| **Parallel exploration** | Both agents tackle the same problem independently, then compare |

The chair (you) decides which dynamic applies per task.

---

## Orchestration & Governance

- **Chair:** Human — you open sessions, interject, redirect, and close. Primary mode is with your involvement.
- **Co-chair (Orchestrator agent):** Role is task-dependent — assigned by the chair at session open based on task type (e.g. Claude orchestrates architecture sessions, Codex orchestrates implementation sessions). Actively moderates the conversation — can recondition it (redirect, refocus, summarize), detect when the discussion is drifting, and escalate to the human when necessary
- **Coordination medium:** Git + local markdown files as shared memory and source of truth
- **Interface metaphor:** Group chat — agents post messages, others respond naturally

### Agent Autonomy

| Action | Autonomy level |
|---|---|
| Reading files, exploring codebase | Fully autonomous |
| Editing local repo files | Allowed within the current session task |
| Git pull | Autonomous — no confirmation needed |
| Git commit | Autonomous within session |
| Git push | Requires explicit human confirmation before executing |
| Any destructive or OT-touching action | Full stop — human must authorize |

### Consensus & Session Close

- **Orchestrator-driven:** the co-chair monitors both agents' messages for agreement signals (matching proposals, no open objections, both approving a direction)
- When it detects consensus, it automatically calls `/pause` and prompts: `[ORCHESTRATOR] Consensus detected on X — confirm /close or /resume to keep discussing`
- You confirm with `/close` → orchestrator writes the summary → git commit
- You can also `/close` manually at any point regardless of consensus state

### Pause & Human Intervention

- **`/pause`** — freezes the conversation immediately; you can read, think, and type without agents responding
- **`/resume`** — unfreeze and continue from where it stopped; full context preserved, no extra tokens
- **Orchestrator auto-pause triggers:** conflicting proposals, ambiguous requirements, pending git push, risky action detected, or consensus reached
- Low friction by design: pausing is instant, context survives, resuming costs nothing extra

---

## Architecture

```
You (chair)
    │
    ▼
roundtable.py   ──── ROUNDTABLE.md (chat log, git-tracked)
    │
    ├── claude --print "..."   → Claude's message (blue)
    └── codex "..."            → Codex's message (green)
```

A single Python script runs in the terminal as the chat room. You type a task to open a session. The orchestrator calls each CLI as a subprocess, streams their replies in a colored terminal chat UI, and appends everything to `ROUNDTABLE.md`. Agents may edit local files when the task requires it, but remote push is always gated by `/push`.

---

## Components

### 1. `roundtable.py` — Orchestrator

- Colored terminal chat UI:
  - Claude = blue
  - Codex = green
  - You (chair) = white
- Invokes both CLIs as subprocesses, captures and parses structured output
- **Human-gated:** you approve each round before the next starts (explicit prompt)
- Commands available mid-session:
  - `/continue` — proceed to next round
  - `/pause` — freeze conversation immediately; you can type freely without triggering agents
  - `/resume` — unfreeze and continue from where it stopped
  - `/close` — end session, write consensus summary, git commit
  - `/summarize` — compress older history to save tokens
  - `/skip [claude|codex]` — skip one agent's turn
  - `/inject <message>` — add a chair message without triggering agent responses
  - `/push` — confirms and executes a pending git push (agents request this, only you can approve)

### 2. CLI Invocations

**Claude** (`~/.local/bin/claude`):
```bash
# First turn in a session
claude -p \
  --output-format json \
  --permission-mode acceptEdits \
  --disallowedTools "Bash(git push*)" \
  --system-prompt "$SYSTEM_PROMPT" \
  --add-dir "$REPO_DIR" \
  "$USER_PROMPT"

# Subsequent turns — native session continuation (token-efficient)
claude -p \
  --output-format json \
  --permission-mode acceptEdits \
  --disallowedTools "Bash(git push*)" \
  --resume "$CLAUDE_SESSION_ID" \
  "$USER_PROMPT"
```

**Codex** (`/usr/local/bin/codex`):
```bash
# First turn — system prompt embedded in prompt body
codex exec --json -C "$REPO_DIR" -s workspace-write -a never "$SYSTEM_PROMPT\n\n$USER_PROMPT"

# Subsequent turns — native session resume
codex exec resume --json "$CODEX_SESSION_ID" "$USER_PROMPT"
```

**Output parsing:**
- Claude → JSON object, extract `.result` or `.content`
- Codex → JSONL event stream, consume until `done` event, extract final text

### 3. `ROUNDTABLE.md` — Shared Chat Log

- Append-only, one entry per message:
  ```
  [CLAUDE] 2026-05-09 14:32
  <message content>

  [CODEX] 2026-05-09 14:33
  <message content>
  ```
- Git-tracked — full session history survives across runs
- Injected as "memory" into each agent's context at the start of their turn

### 4. Context Window (Token Efficiency)

- **Rolling window:** last 5 exchanges sent to each agent per turn (configurable)
- **`/summarize` command:** compresses older history into a short paragraph, replaces it in the log
- Keeps per-turn token cost predictable and bounded
- Task description injected once at session start, not repeated every turn

### 5. System Prompts (Lean)

**Claude** — injected via `--system-prompt` flag:
> "You are [Claude|Codex], participating in a developer round table on the TFG-Alumbrado project (read-only FINS/UDP gateway, Python/SQLAlchemy, RPi). Contribute your perspective on the current task. Be concise. Do not repeat what was already said. You may inspect and edit the local repo when the task requires it, but do not push to GitHub. If you need the human's input, write [ESCALATE]: reason. If you believe consensus is reached, write [CONSENSUS]: summary."

**Codex** — no `--system-prompt` flag; embed instructions at the top of the first prompt, then rely on session resume for subsequent turns. Same content as above.

**Task description** prepended to the first message only — not repeated every turn.

### 6. Session Lifecycle

```
OPEN
  └── You type a task description
       └── Logged to ROUNDTABLE.md
            └── Claude responds first
                 └── Codex responds
                      └── You read both → /continue or /close

ROUND N
  └── You type /continue (or a new message)
       └── Both agents get rolling context + new input
            └── Respond in sequence
                 └── You moderate

CLOSE
  └── You type /close
       └── One agent writes consensus summary
            └── Appended to ROUNDTABLE.md
                 └── Git commit: "roundtable: <task title> — session closed"
```

---

## File Structure (target)

The orchestrator is project-agnostic and lives in `claude-code/`. Only session artifacts land in the project repo.

```
/Users/juansebastian/claude-code/
├── roundtable/
│   ├── roundtable.py        # orchestrator script (reusable across projects)
│   └── config.json          # defaults: window size, agent order, colors
└── designs/
    └── roundtable-design.md # this file

/Users/juansebastian/alumbrado-gateway-receival/TFG-Alumbrado/
├── ROUNDTABLE.md            # live chat log (git-tracked, project-specific)
└── .roundtable/
    └── sessions/            # archived session logs (one per closed session)
```

---

## Open Items

- [x] Git repo initialized and connected via SSH
- [x] Project codebase context added
- [x] Co-chair policy: task-dependent, assigned by chair at session open
- [x] Script location: roundtable.py in claude-code/, logs in TFG-Alumbrado/
- [x] Consensus: orchestrator detects and auto-pauses for human confirmation
- [x] Local repo edits allowed during the current session task; git push remains human-gated
- [x] Claude invocation: `claude -p --output-format json --permission-mode acceptEdits --disallowedTools "Bash(git push*)" --system-prompt "..." --add-dir $REPO`; continuation via `--resume`
- [x] Codex invocation: `codex exec --json -C $REPO -s workspace-write -a never "..."`; continuation via captured session ID, with `resume --last` only as fallback
- [x] Output parsing: Claude → JSON, Codex → JSONL event stream
- [x] Codex system prompt: embedded in first prompt body (no flag available)
- [x] Consensus/escalation signals: agents write `[CONSENSUS]:` or `[ESCALATE]:` tags
- [x] Agent order: chair drops a name ("Claude" / "Codex") to designate first speaker; if no name given, orchestrator decides based on task context

---

## Next Steps (after git is ready)

1. Confirm open items above
2. Write implementation plan (`writing-plans` skill)
3. Build `roundtable.py` incrementally — start with basic subprocess calls + file logging, then add the chat UI
