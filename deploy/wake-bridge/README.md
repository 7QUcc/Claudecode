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
session, cold-start a session, or inject through the xiaoke frontend. The
adapter is experimental; verify a new launched session before changing the
existing xiaoke session startup path.

The checked-in manifest template is
`host-adapters.json.example`. It contains no credentials.
