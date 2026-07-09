# AGENTS.md — context pointer for non-Claude agents (Gemini / Antigravity / etc.)

This project is worked on by BOTH Claude Code and Google Antigravity (Gemini).
The canonical context lives in **`CLAUDE.md`** in this same directory — read it in full,
especially the **`## Active Handoff`** section at the bottom for current state.

Also read the global context at **`~/.claude/CLAUDE.md`** (network IPs, shared secrets
path, SSH, and the dual-model workflow rules).

## Conventions for any AI working here
- **Secrets**: never hardcode. Read `~/projects/secrets.env` (or this project's `.env`).
  NEVER write a secret value into `CLAUDE.md`/`AGENTS.md` — both are in git.
- **Dry-run first**: show a plan before changing code, config, or live state; wait for
  approval; then execute.
- **Handoff**: before finishing, update `## Active Handoff` in `CLAUDE.md` with the
  current state, tagged with the date + your model name, e.g. `[2026-07-08 (Antigravity)]`.
- **Artifacts**: write any analysis/reports INTO this repo (e.g. `./docs/` or `./handoff/`),
  NOT to `~/.gemini/.../brain/` — Claude Code cannot see that directory.
