# ADR 0003: Typed envelopes on the repository protocol

Date: 2026-07-11 · Status: accepted · Trigger: review finding #7

## Context

The `SpotifyRepository` protocol - whose stated purpose is enabling a second
provider - returned `dict[str, Any]` envelopes and mixed live pydantic models
(paged reads) with pre-dumped dicts (`currently_playing`, `recently_played`).
Implementing the protocol required reverse-engineering shapes from
`SpotifyApiRepository`'s body, defeating the abstraction's purpose.

## Decision

- `Page[T]`, `NowPlaying`, `PlayedItem` TypedDicts (in `models/schemas.py`)
  define the envelope contracts. Zero runtime cost; pyright enforces shapes
  on every implementer, including the test fake.
- One convention: **live models flow through repository and service; dicts
  appear only at the tool boundary** (`model_dump` in `tools/definitions.py`).
- Exception: `search` stays `dict[str, Any]` - its shape is heterogeneous
  per requested type; the contract is documented in the tool reference. A
  TypedDict-per-type-combination would be ceremony without a consumer.

## Consequences

- A second provider can be written from the protocol's signatures alone.
- This respects the standing "pydantic for 3 models only" decision: TypedDicts
  are annotations, not a modeling layer.
