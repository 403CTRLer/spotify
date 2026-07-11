# Recovery guide: snapshots, restore, failure modes

## The snapshot mechanism

Destructive playlist rewrites (`shuffle`, `shuffle-all`) write a **recovery
snapshot before touching anything**:

- Location: `~/.spotify-mcp/recovery/{playlist_id}-{unix_timestamp}.json`
- Contents:

```json
{
  "playlist_id": "37i9dQZF1DXcBWIGoYBM5M",
  "name": "My Mix",
  "uris": ["spotify:track:…", "…"],
  "skipped": ["spotify:local:…"]
}
```

- `uris` is the **full** streamable track list in original order.
- `skipped` lists local/unavailable entries that a rewrite cannot restore.
- On success the snapshot is deleted. **A leftover snapshot file means a
  rewrite failed mid-flight** and the error message names the file.

## Restoring

```sh
uv run spotify-mcp restore ~/.spotify-mcp/recovery/<file>.json
```

This replaces the playlist's contents with the snapshot's `uris` and deletes
the snapshot on success. Safety rules:

- **Post-snapshot edits are detected**: if the playlist contains tracks that
  are not in the snapshot (someone added music after the failure), restore
  refuses with `RestoreConflictError`; `--force` overwrites deliberately.
  The normal failure state - a playlist that is a partial subset of the
  snapshot - restores without friction.
- Malformed snapshot files are rejected and never deleted.
- Entries in `skipped` cannot be restored via the Web API - re-add local
  files from a Spotify desktop client.

## Failure modes, by operation

| Operation | Destructive step | Protection |
|---|---|---|
| `shuffle` | replace-PUT + append chunks | snapshot before mutation; replace-PUT means the playlist is never empty mid-flight; on failure the error names the snapshot |
| `shuffle` on a playlist with local tracks | rewrite would drop them permanently | **refused** with `LocalTracksError` unless `--force`; with `--force` the dropped entries are recorded in the snapshot |
| `shuffle-all` | per-playlist shuffle | playlists with local tracks are reported as `skipped` and left untouched |
| `mix` | none | additive-only since 0.2.0: nothing is ever removed, so a mid-flight failure leaves at worst a partial append |
| `liked-to-playlist` | none | additive-only |
| `clear-liked` | deletes all saved tracks | strict y/yes confirmation in the CLI; EOF counts as refusal; **no snapshot exists for saved tracks** - this is genuinely irreversible |
| `restore` | replace-PUT | refuses when post-snapshot edits detected (unless `--force`); consumes the snapshot only on success |
| `delete-playlist` / `delete_playlist` tool | unfollow | y/N prompt (CLI) or confirm protocol (MCP); Spotify keeps deleted playlists recoverable ~90 days |
| MCP `shuffle_playlist` | as CLI shuffle | two-step confirm protocol on top of snapshot + local-track guard |

## What is NOT protected

- `clear-liked` has no undo. The confirmation prompt is the only gate.
- Concurrent writers (another app editing the playlist during a shuffle) can
  interleave; the snapshot restores the pre-shuffle state, discarding their
  edits.
- Snapshots from failed runs accumulate in `~/.spotify-mcp/recovery/`;
  deleting one is safe once you no longer need the restore point.
