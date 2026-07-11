# User guide (CLI reference)

All commands run as `uv run spotify-mcp …` (or `spotify-mcp …` in an active
venv). Global flags (before the subcommand): `-v`/`-vv` (INFO/DEBUG logs to
stderr), `--json` (machine-readable stdout on read commands - pipe-friendly).

References can be **URLs** (`https://open.spotify.com/...`, query strings and
locale segments handled), **URIs** (`spotify:playlist:…`), or **bare
22-character IDs** where the type is implied by the command.

Exit codes: `0` success · `1` domain error (stderr) or refused confirmation ·
`2` bad arguments · `130` interrupted.

## Setup

```sh
uv run spotify-mcp auth      # browser PKCE login; tokens -> ~/.spotify-mcp/
uv run spotify-mcp serve     # run the MCP server on stdio
```

## Playback (requires Spotify Premium)

```sh
uv run spotify-mcp now                       # state + devices ('*' = active)
# Playing: Kids - MGMT  [Desk]
#   * Desk (Computer)  vol=60
#     Phone (Smartphone)  vol=30

uv run spotify-mcp play                                  # resume
uv run spotify-mcp play spotify:album:AAA…               # play an album
uv run spotify-mcp play 4uLU6hMCjMI75M1A2tKUQC           # bare ID = track
uv run spotify-mcp play spotify:playlist:PPP… --device <id-from-now>
uv run spotify-mcp pause
uv run spotify-mcp next
uv run spotify-mcp prev
uv run spotify-mcp queue https://open.spotify.com/track/TTT…
uv run spotify-mcp volume 40
```

Non-Premium accounts get Spotify's 403 message on control commands; `now`
works for everyone.

## Discovery and library

```sh
uv run spotify-mcp search "bicep glue" --type track --type album --limit 5
uv run spotify-mcp lookup https://open.spotify.com/album/AAA…
uv run spotify-mcp top tracks --range short --limit 10   # ~4 weeks
uv run spotify-mcp top artists --range long
uv run spotify-mcp recent --limit 20
uv run spotify-mcp like spotify:track:TTT… spotify:track:UUU…
uv run spotify-mcp unlike spotify:track:TTT…
uv run spotify-mcp --json top tracks | jq '.[].name'     # shell pipelines
```

## Playlists

```sh
uv run spotify-mcp playlists                             # list yours
uv run spotify-mcp tracks spotify:playlist:PPP… --limit 50
uv run spotify-mcp create-playlist "Road Trip" --description "loud" --public
uv run spotify-mcp update-playlist PPP… --name "Road Trip 2" --private
uv run spotify-mcp delete-playlist PPP…                  # asks y/N; 90-day recovery
uv run spotify-mcp mix SRC1 SRC2 --into TARGET           # additive: never removes
uv run spotify-mcp liked-to-playlist TARGET
```

## Shuffle and recovery

```sh
uv run spotify-mcp shuffle spotify:playlist:PPP…
uv run spotify-mcp shuffle PPP… --force        # allow dropping local tracks
uv run spotify-mcp shuffle-all --ignore "chill,https://open.spotify.com/playlist/…"
uv run spotify-mcp restore ~/.spotify-mcp/recovery/PPP…-1752192000.json
uv run spotify-mcp restore <snapshot> --force  # overwrite post-snapshot edits
```

- `shuffle` snapshots the full track list to `~/.spotify-mcp/recovery/`
  **before** touching anything and deletes it on success; a failed run names
  the snapshot file.
- Playlists containing local/unavailable tracks refuse to shuffle (a rewrite
  would permanently drop them); `--force` overrides and records the dropped
  entries in the snapshot. `shuffle-all` skips such playlists.
- `restore` refuses when the playlist gained tracks after the snapshot
  (they would be removed); `--force` overwrites.
  Full failure-mode table: [recovery.md](recovery.md).

## Destructive: clear-liked

```sh
uv run spotify-mcp clear-liked
# Delete ALL 812 saved tracks? This cannot be undone. [y/N]
```

Only `y`/`yes` proceeds; closed stdin counts as refusal. There is **no
snapshot** for saved tracks - this one is genuinely irreversible.

## Rate limits

Development-mode apps are throttled aggressively. Short waits are retried
automatically; when Spotify demands a wait beyond 30s the command fails fast
and reports how long to wait.
