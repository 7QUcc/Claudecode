# xk-applogger MCP

The server is configured for the `cc` user's Claude Code `user` scope:

- Endpoint: `https://xk-applogger.up.railway.app/mcp`
- Server: `device-event-logger` 1.1.0
- Tools: `query_events`, `list_event_types`, `delete_events`

Install or restore with:

```sh
claude mcp add --scope user --transport http xk-applogger \
  https://xk-applogger.up.railway.app/mcp
```

Remove it with:

```sh
claude mcp remove xk-applogger --scope user
```

The endpoint is public and currently does not require an API key. Do not add
credentials to this file. The live Claude config is `/home/cc/.claude.json`;
installation backups are kept beside that file on the server.
