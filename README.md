# Agentic Memory Orchestrator

Local, long-term memory for coding agents. A small MCP server that lets an agent (Cursor, or any MCP client) save what it learned in a session and recall it in the next one, without the agent ever writing to the database directly.

## How it works

The agent proposes memory; the server decides what gets stored.

```text
Agent (Cursor / any MCP client)
   │  proposes MemoryCandidates over MCP
   ▼
Memory service ── validate → transform → dedupe / conflict check
   │
   ▼
SQLite (source of truth) ──► Obsidian vault (optional, generated, read-only view)
```

Four kinds of memory, each with its own rules:

| Type | Answers | Example |
| --- | --- | --- |
| Working state | What are we doing now? | focus, known facts, hypotheses, next actions |
| Episode | What happened? | "Services could not reach the database until ingress was fixed." |
| Semantic | What do we believe is true? | `architecture.database / postgres.application_ingress` |
| Lesson | How should the agent behave? | WHEN timeout / DO inspect firewall rules / BECAUSE recurring failure |

The server, not the model, owns ids, timestamps, source attribution, and importance. The agent scores five 0–3 dimensions (future usefulness, cost of rediscovery, blast radius, decision significance, recurrence); the server sums them into `low` / `normal` / `high` / `critical`. A semantic memory with an existing key is never silently overwritten: the same statement is linked as supporting evidence, a different one is returned as a `conflict`. Every candidate gets an explicit outcome: `created`, `linked`, `duplicate`, `conflict`, `rejected` (with reason), or `ignored`.

The full design is in [`docs/`](docs): [schema](docs/memory-schema.md), [orchestration](docs/memory-orchestration.md), the [agent contract](docs/memory-agent-contract.md) agents must follow, and [decision records](docs/decisions).

## Status and plans

Working today: SQLite store, four MCP tools (`get_memory_context`, `get_memory_status`, `submit_memory_candidates`, `sync_obsidian`), Obsidian sync, a setup CLI, and two Cursor skills (`/memory-save`, `/memory-status`).

Next, in order (details in [ROADMAP.md](docs/ROADMAP.md)):

1. `/memory-close`: consolidate a work period from stored memory in a fresh chat and write a handoff.
2. Consolidation tools: semantic revisions (expand, correct, split, dispute, supersede) with review for risky changes.
3. Local embeddings (for example via Ollama) for related-memory lookup and ranked recall.
4. An evaluation set to measure which models can be trusted with which memory operations.

No frontier-model API key is required: reasoning happens in your existing agent, and the server stays deterministic.

## Setup

Requires Python 3.11+.

```bash
git clone <this repo> agentic-memory-orchestrator
cd agentic-memory-orchestrator
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Create a database and a project. The command prints the values you need next.

```bash
agent-memory --db data/dev/memory.db init --name "My Project" \
  --repo-path ~/code/my-project \
  --obsidian-path ~/Documents/MyProjectVault   # optional
agent-memory --db data/dev/memory.db projects    # list projects later
```

### Configuration

All settings are environment variables, normally set in the MCP config `env` block.

| Variable | Purpose | Default |
| --- | --- | --- |
| `AGENT_MEMORY_DB` | SQLite file path | `data/dev/memory.db` (the launcher script resolves it inside this repo) |
| `AGENT_MEMORY_PROJECT_ID` | Project used when a tool call omits `project_id` | none; tools then require `project_id` |
| `AGENT_MEMORY_VAULT` | Obsidian vault used when the project has no `obsidian_path` | none; vault sync is skipped |
| `AGENT_MEMORY_CLIENT` | Recorded as `submitted_by`; `manual` marks memory as developer-explicit | `mcp` |

Use separate database files for experiments and real memory (for example `data/dev/` and `data/live/`). `data/` is gitignored.

### Connect Cursor in this repo

Edit [`.cursor/mcp.json`](.cursor/mcp.json) and replace the placeholder with your project id:

```json
{
  "mcpServers": {
    "agent-memory": {
      "command": "${workspaceFolder}/scripts/agent-memory-mcp",
      "env": { "AGENT_MEMORY_PROJECT_ID": "prj_..." }
    }
  }
}
```

### Use it from another project

Point that project's `.cursor/mcp.json` at this checkout, with an absolute database path:

```json
{
  "mcpServers": {
    "agent-memory": {
      "command": "/absolute/path/to/agentic-memory-orchestrator/scripts/agent-memory-mcp",
      "env": {
        "AGENT_MEMORY_DB": "/absolute/path/to/memory.db",
        "AGENT_MEMORY_PROJECT_ID": "prj_..."
      }
    }
  }
}
```

If you installed the package, `"command": "agent-memory-mcp"` works too. Then copy `.cursor/skills/memory-save` and `.cursor/skills/memory-status` into that project, along with `docs/memory-agent-contract.md` (or update the contract path inside `memory-save/SKILL.md`). One database can hold many projects; give each repo its own `AGENT_MEMORY_PROJECT_ID`.

Other MCP clients can launch the same command over stdio.

### Day-to-day use

- `/memory-save` after a meaningful finding: a root cause, a confirmed fix, a decision. The agent reads current context, proposes candidates, and reports each outcome.
- `/memory-status` to see what the server currently holds, read-only.
- Open the vault in Obsidian to browse notes with `[[wikilinks]]` between related memories. Vault files are regenerated on every save, so edit memory through the agent, not the notes.

## Results and tests

```bash
pytest -q   # 115 passed in under 1 second
```

| Area | Tests | What they prove |
| --- | --- | --- |
| Models and identifiers | 63 | Required fields, enums, prefixed ULIDs, importance must match its dimensions, link ids match their types |
| Validation and transformation | 23 | Facts rejected as lessons, events rejected as facts, hypotheses kept out of `known`, server-owned fields refused |
| Storage | 7 | Migrations, round-trips, project isolation, unique semantic keys, one working state per project, links need real typed endpoints |
| Memory service | 6 | Create, conflict, and reject routing (rejects write nothing); working-state replacement; vault skipped or failing never undoes a save |
| Obsidian sync | 4 | Notes and wikilinks, stable re-sync, removal of stale generated notes only, path required |
| MCP server | 8 | Exactly four tools exposed, default-project fallback, clear errors for missing or unknown projects |
| CLI | 4 | Project creation, listing, env-based database path |

All tests use temporary databases and never touch `data/`. An end-to-end check over real stdio (CLI init, launcher script, save, status, vault write) was also run during setup and behaved as expected, including rejecting a fact submitted as a lesson.

What the tests do not show yet:

- **Memory quality.** Nothing measures whether agents choose the right memories or whether recall improves later sessions. That is the purpose of the planned evaluation set.
- **Validator precision.** Business validation uses keyword rules, so it is strict and sometimes wrong. A valid fact containing "deployed" is rejected as an event; "local" or "production" without a `scope` is rejected; lesson instructions must start with one of 26 listed verbs, so "Call …" fails; two events joined by "plus" are accepted as one. Rejections come back with a reason, so the agent can rephrase, but expect some friction.
- **Recall ranking.** Context is everything active for the project plus recent episodes; there is no relevance search until embeddings land.
- **Untested paths.** Duplicate and supporting-evidence linking, atomic multi-record writes, and the guard against writing outside the vault are implemented but have no dedicated tests yet.

## Layout

```text
src/
  models/          Pydantic schemas and enums
  validation.py    business rules per memory type
  transformation.py candidate → stored record
  storage.py       SQLite repository and migrations
  memory_service.py routing, dedupe, conflicts, working state
  obsidian_sync.py vault rendering
  mcp_server.py    MCP tools
  cli.py           agent-memory init / projects
  config.py        environment settings
scripts/agent-memory-mcp   stdio launcher
.cursor/           MCP config and skills
docs/              design, contract, roadmap, decisions
tests/
```

## Acknowledgements

The memory split (semantic, episodic, lessons, Obsidian sync) is inspired by [kiro-recall](https://github.com/fredluckham/kiro-recall).
