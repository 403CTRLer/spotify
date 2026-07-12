# Connecting MCP clients

The server speaks stdio MCP, so any compliant client works the same way:
launch `spotify-mcp serve` as a subprocess. Complete `spotify-mcp auth` once
in a terminal before connecting a client - the server itself never opens a
browser (see [oauth.md](oauth.md)).

Generic config shape used by most clients:

```json
{
  "mcpServers": {
    "spotify": {
      "command": "uv",
      "args": ["run", "spotify-mcp", "serve"],
      "cwd": "/path/to/this/repo"
    }
  }
}
```

If your `uv` environment or working directory isn't guaranteed at launch
time, set `SPOTIFY_CLIENT_ID`/`SPOTIFY_REDIRECT_URI` via the config's `env`
block instead of relying on `.env` discovery (`Settings.from_env` also falls
back to `~/.spotify-mcp/.env`, which is cwd-independent):

```json
{ "command": "uv", "args": ["run", "spotify-mcp", "serve"],
  "env": { "SPOTIFY_CLIENT_ID": "your-client-id" } }
```

## Claude Desktop / Claude Code

Claude Desktop: Settings → Developer → Edit Config, add the block above under
`mcpServers` in `claude_desktop_config.json`.

Claude Code: `claude mcp add spotify -- uv run spotify-mcp serve` (run from
this repo), or add the same block to `.mcp.json` / your user config.

## Cursor

Settings → MCP → Add new MCP server, or add the same block to
`~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (per-project).

## VS Code (Cline, Roo Code)

Both extensions read an `mcpServers` (Cline) or `mcp.json`-shaped
(VS Code's native MCP support) config from their settings UI or a workspace
file - use the generic block above under the extension's "MCP Servers"
settings entry.

## OpenHands

Add the block under `mcp.stdio_servers` in your OpenHands config (`config.toml`
or the UI's MCP settings), using the same `command`/`args`.

## Any other stdio-compatible client

If a client can launch an arbitrary command and speak MCP over its stdin/
stdout, the generic block works unchanged - there is nothing
Claude-specific, Cursor-specific, etc. in this server.

## Verifying the connection

```sh
npx @modelcontextprotocol/inspector uv run spotify-mcp serve
```

Lists every tool with its schema and annotations; call `user_profile` to
confirm authentication is wired up correctly.
