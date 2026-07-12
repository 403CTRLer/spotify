# User guide (CLI reference)

All commands run as `uv run spotify-mcp …` (or `spotify-mcp …` in an active
venv). Global flags (before the subcommand): `-v`/`-vv` (INFO/DEBUG logs to
stderr), `--json` (machine-readable stdout on read commands - pipe-friendly).

References can be **URLs** (`https://open.spotify.com/...`, query strings and
locale segments handled), **URIs** (`spotify:playlist:…`), or **bare
22-character IDs** where the command's argument names the type. `mix` sources
and `lookup` require a URL or URI (the type would otherwise be ambiguous).

Exit codes: `0` success · `1` domain error (stderr) or refused confirmation ·
`2` bad arguments · `130` interrupted.

## Authentication

```sh
uv run spotify-mcp auth      # browser PKCE login; tokens -> ~/.spotify-mcp/
uv run spotify-mcp serve     # run the MCP server on stdio
```

See [oauth.md](oauth.md) for the flow and scopes.

## User Profile

Exposed only via the `user_profile` MCP tool and implicitly through commands
like `playlists`/`create-playlist` that need the current user; there is no
standalone `whoami` command (no demand yet).

## Search

```sh
uv run spotify-mcp search "bicep glue" --type track --type album --limit 5
uv run spotify-mcp lookup https://open.spotify.com/album/AAA…
```

## Library

```sh
uv run spotify-mcp recent --limit 20
uv run spotify-mcp like spotify:track:TTT… spotify:track:UUU…
uv run spotify-mcp unlike spotify:track:TTT…
uv run spotify-mcp top tracks --range short --limit 10   # ~4 weeks
uv run spotify-mcp top artists --range long
uv run spotify-mcp --json top tracks | jq '.[].name'     # shell pipelines
```

`clear-liked` removes **every** saved track and has no snapshot - the one
genuinely irreversible operation in this tool:

```sh
uv run spotify-mcp clear-liked
# Delete ALL 812 saved tracks? This cannot be undone. [y/N]
```

Only `y`/`yes` proceeds; closed stdin counts as refusal.

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

`mix` merges playlist and/or track sources into a destination: existing
target tracks are left in place, only new tracks are appended (shuffled), and
nothing is ever removed - a failed run can only under-add, never lose data.
Batch writes respect Spotify's documented limits (100 tracks per add
request) and the client's built-in retry/backoff for rate limits.

### Shuffle

```sh
uv run spotify-mcp shuffle spotify:playlist:PPP…
```

Reorders every track **in place** using Spotify's playlist-reorder operation
- no track is ever removed or re-added, so nothing can be lost, including
local files. It costs about one API request per track, so large playlists
take a while, and a mid-run failure just leaves the playlist partially
shuffled (never incomplete).

## Playback

Requires a **Spotify Premium** account for control commands; `now` works for
everyone.

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

Non-Premium accounts get Spotify's own 403 message on control commands.

## Rate limits

Development-mode apps are throttled aggressively. Short waits are retried
automatically; when Spotify demands a wait beyond 30s the command fails fast
and reports how long to wait.
