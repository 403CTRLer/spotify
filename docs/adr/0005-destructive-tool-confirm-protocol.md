# ADR 0005: Two-step confirm protocol for destructive MCP tools

Date: 2026-07-12 · Status: accepted · Trigger: production-readiness review
(re-evaluation of "no destructive MCP tools")

## Context

0.2.0 deliberately kept destructive operations CLI-only. That protected users
but made the MCP server strictly weaker than the CLI for legitimate requests
("shuffle my workout playlist", "delete that empty playlist"). An LLM caller
cannot be trusted with single-call destructive tools, but it can follow a
stateless confirmation handshake.

## Decision

Destructive tools take a `confirm: bool = false` parameter:

1. **First call (no confirm)**: the tool fetches the target, returns a
   preview naming it and the blast radius ("this will permanently reorder all
   184 tracks of 'Road Trip'"), states that **no changes were made**, and
   instructs the caller to repeat with `confirm=true`. The model must
   surface this to the human.
2. **Second call (`confirm=true`)**: executes, with the same underlying
   safeguards as the CLI (recovery snapshot before shuffle, local-track guard
   with explicit `force`, 90-day playlist recovery noted for delete).

Applied to `shuffle_playlist` and `delete_playlist`. NOT applied to additive
operations (mix-like adds, queue, save) or reversible metadata edits
(`update_playlist`). `clear-liked` (delete all saved tracks) remains
CLI-only: it is irreversible, has no snapshot, and no MCP use case justifies
the risk.

The protocol is stateless (no server-side pending-confirmation registry) so
it works across MCP clients and reconnects; the cost is that a caller could
send `confirm=true` first - accepted, since the CLI's `--force`-style flags
have the same property and the human-in-the-loop is the MCP client's
responsibility.

## Consequences

- MCP parity with the CLI for the operations users actually ask for.
- Tool descriptions carry the protocol so models discover it without docs.
- Tests assert the first call makes zero mutating calls.
