# Wake Bridge deployment

The server uses the upstream `wake-bridge@preview` package and the bundled
experimental Claude CLI channel adapter.

## Server layout

- Runtime: `/home/cc/.local`
- Agent Space: `/home/cc/.local/state/wake-bridge/default`
- Daemon: `io.wakebridge.default.service`
- Listener: `127.0.0.1:4311` only
- Host manifest: `host-adapters.json`
- Secret environment file: `daemon.env` (not tracked)

The Agent Space config, owner credential, host bootstrap token, SQLite database,
and service environment file are private server state and must never be
committed.

## Install or upgrade

Run as `cc` with Node.js 20+ and SQLite 3.33+ available:

```sh
npm install --global --prefix "$HOME/.local" wake-bridge@preview
wakebridge release-preflight --config "$HOME/.local/state/wake-bridge/default/wakebridge.config.json"
```

Before an existing database upgrade, stop the user service and run the
upstream `wakebridge backup` / `wakebridge upgrade` workflow. Do not delete the
Agent Space directory during package upgrades.

## Claude adapter boundary

The upstream adapter only supports a Claude Code TTY explicitly launched by
`wakebridge-claude launch`. It does not attach to an already running Claude
session or cold-start one. When Wake Bridge is installed, xiaoke creates new
Claude TTY sessions through the launcher. `claude-host.sh` adds only xiaoke's
session settings and, when selected, the official Telegram channel. It does
not replace the launcher's generated Wake Bridge MCP and channel configuration.

Only one running Claude session should own the Telegram bot. A new session
must opt in to Telegram, and the previous holder must release it first. The
Host token is sourced from the private `daemon.env` inside the tmux pane so a
long-lived tmux server does not need to inherit it. Existing sessions must be
recreated through the launcher; they cannot be attached retroactively.
For a Telegram-enabled session, only `TELEGRAM_BOT_TOKEN` is extracted from
the existing private xiaoke `.env`; the dashboard password is not inherited.

The checked-in manifest template is
`host-adapters.json.example`. It contains no credentials.
