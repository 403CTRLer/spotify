# ADR 0007: Capability registry as the single source of truth for the tool surface

Date: 2026-07-12 · Status: accepted · Trigger: production-readiness reuse pass

## Context

Tool behavior metadata (read-only vs. destructive, idempotency, confirmation
requirements, required OAuth scopes) was implicit in each tool's docstring
and scattered across `mcp/server.py`, `auth/oauth.py`'s `SCOPES` constant,
and prose in the docs. Nothing enforced that a new tool declared its scope,
that `SCOPES` matched what tools actually used, or that MCP clients received
accurate `ToolAnnotations` for autonomy decisions. The brief also asked for
a stable, capability-described surface rather than one defined by counting
tools.

## Decision

- `tools/capabilities.py` defines a `Capability` dataclass (`read_only`,
  `destructive`, `idempotent`, `confirmation_required`, `scopes`) and a
  `CAPABILITIES: dict[str, Capability]` keyed by tool name - one declaration
  per tool, independent of the tool function itself.
- `mcp/server.py` builds `mcp.types.ToolAnnotations` from the registry at
  registration time (`readOnlyHint`, `destructiveHint`, `idempotentHint`,
  `openWorldHint=True` for all - every tool calls an external API).
- Three tests keep the registry honest: it covers exactly the tools in
  `ALL_TOOLS` (no orphans in either direction); the union of declared scopes
  equals `auth.SCOPES` exactly (scope drift - added or stale - fails CI); and
  every `confirmation_required` tool (and only those) exposes a `confirm`
  parameter.
- Documentation (tool reference, api-coverage, security, oauth) is organized
  around capability categories (Authentication, Library, Playlists, Playback,
  Search, User Profile) rather than a tool count, so it doesn't need updating
  every time a tool is added or removed.

## Consequences

- Adding a tool without declaring its capability fails a test immediately,
  rather than silently shipping unannotated or under-scoped.
- The registry lives in its own module, decoupled from `tools/definitions.py`
  (per explicit review guidance), so capability metadata can be read or
  audited without importing tool implementations.
