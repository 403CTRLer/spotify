# User guide

All commands run as `uv run spotify-mcp …` (or `spotify-mcp …` if the venv is
active). Global flags: `-v` (INFO logs), `-vv` (DEBUG logs), both to stderr.

Playlist/track references can be **URLs** (`https://open.spotify.com/playlist/…`,
query strings and locale segments handled), **URIs** (`spotify:playlist:…`),
or **bare 22-character IDs** where the type is implied by the command.

## Setup commands

### `auth` - log in via browser (PKCE)

```sh
uv run spotify-mcp auth
# Opening browser… → sign in → "Logged in as <name>"
```

Requires `SPOTIFY_CLIENT_ID` in the environment, `./.env`, or
`~/.spotify-mcp/.env`. Tokens land in `~/.spotify-mcp/tokens.json`.

### `serve` - run the MCP server (stdio)

```sh
uv run spotify-mcp serve
```

See the README for MCP client configuration and
[tool-reference.md](tool-reference.md) for the 10 tools.

## Library and playlist commands

### `playlists` - list your playlists

```sh
uv run spotify-mcp playlists
# Road Trip  (184 tracks)  [37i9dQZF1DXcBWIGoYBM5M]
```

### `mix` - merge sources into a playlist (additive)

```sh
uv run spotify-mcp mix \
  https://open.spotify.com/playlist/AAA… spotify:album:BBB… \
  --into https://open.spotify.com/playlist/TTT…
# Added 42 unique tracks (7 duplicates skipped).
```

Sources may be playlists, albums, or single tracks (bare IDs are assumed to be
playlists). Since 0.2.0 mix **never removes anything**: tracks already in the
target stay in place and count as duplicates; only new tracks are appended,
in shuffled order. Local tracks in sources are skipped (the API cannot add them).

### `shuffle` - persistently shuffle one playlist

```sh
uv run spotify-mcp shuffle spotify:playlist:AAA…
# Shuffled 184 tracks.
```

A full-track-list snapshot is written to `~/.spotify-mcp/recovery/` first and
deleted on success. If the playlist contains **local or unavailable tracks**,
the command refuses (they would be permanently lost); add `--force` to shuffle
only the streamable tracks - the dropped entries are recorded in the snapshot.

### `shuffle-all` - shuffle every playlist you own

```sh
uv run spotify-mcp shuffle-all --ignore "chill, https://open.spotify.com/playlist/AAA…"
# shuffled: Road Trip
#  ignored: Chill Vibes
#  skipped (contains local/unavailable tracks): Old MP3s
```

`--ignore` accepts links, URIs, IDs, or case-insensitive name fragments,
comma-separated or repeated. An empty ignore list ignores nothing. Playlists
with local tracks are skipped, never forced.

### `restore` - recover from a failed rewrite

```sh
uv run spotify-mcp restore ~/.spotify-mcp/recovery/AAA…-1752192000.json
# Restored 184 tracks to 'Road Trip'.
```

See [recovery.md](recovery.md).

### `liked-to-playlist` - copy all liked songs into a playlist

```sh
uv run spotify-mcp liked-to-playlist spotify:playlist:TTT…
# Added 812 liked tracks.
```

### `clear-liked` - remove ALL liked songs (destructive)

```sh
uv run spotify-mcp clear-liked
# Delete ALL 812 saved tracks? This cannot be undone. [y/N] y
# Removed 812 saved tracks.
```

Only `y`/`yes` proceeds; anything else (including closed stdin) aborts.
There is no snapshot for saved tracks - this is irreversible.

## Exit codes

`0` success · `1` domain error (message on stderr) or refused confirmation ·
`2` bad arguments (argparse) · `130` interrupted.

## Rate limits

Development-mode Spotify apps are throttled aggressively. Short waits are
retried automatically; when Spotify demands a wait longer than 30s the command
fails fast and tells you how long to wait.
