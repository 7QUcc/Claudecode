# CcCompanion server deployment

The upstream checkout lives at `/home/cc/CcCompanion`. Its Python environment is
`/home/cc/CcCompanion/apns-server/.venv`. The server runs as `cc` through
`cccompanion.service` and connects to the `CcCompanion` tmux session.

The service binds only the server's Tailscale address on port 8795. Tailscale is
configured with `--accept-routes=false --accept-dns=false` and no exit node.
It is signed into the iPhone's `R7` Tailnet, not the earlier Gmail Tailnet.
`tailscaled` has no HTTP/SOCKS proxy override; the Mihomo DNS configuration
exempts `+.tailscale.com` from fake-IP and resolves it through
`https://223.5.5.5/dns-query`. The previous Mihomo configuration is backed up
at `/etc/mihomo/config.json.bak.tailscale-20260927`.

Install `cccompanion-config.toml` as
`/home/cc/CcCompanion/apns-server/config.toml` with owner `cc` and mode 0600.
The upstream server creates its shared secret at `/home/cc/.ots/secret` with
mode 0600. Neither the secret nor APNs credentials belong in Git.

Merge the CcCompanion Stop hook from `claude-session-settings.json` into the
live `/home/cc/.claude/settings.json`; do not replace the entire live file.
The Stop hook posts replies back to the private server URL and reads the shared
secret from `/home/cc/.ots/secret`.

Health checks:

```sh
systemctl status cccompanion tailscaled
sudo -u cc tmux list-sessions
curl http://100.68.76.100:8795/health
ip -4 route get 1.1.1.1
```

The URL is a private Tailnet address, not a public endpoint. If Tailscale assigns
a different address, update both `cccompanion-config.toml` and the Stop hook URL
in `claude-session-settings.json`, then redeploy and restart the affected service
and Claude session. APNs push is disabled until valid Apple credentials are
configured; chat polling works without them.

The old iPhone Tailnet entry at `100.112.86.1` is an offline device and is not
the current server. Update the CcCompanion wizard to use
`http://100.68.76.100:8795`; keep the existing shared secret.

The pre-switch server configuration is backed up at
`/home/cc/CcCompanion/apns-server/config.toml.bak.tailnet-20260927`, and the
pre-hook Claude settings at `/home/cc/.claude/settings.json.bak.cccompanion-20260927`.
To restore the earlier Gmail Tailnet deployment, run `tailscale switch 8917`,
restore those two backups, and restart `cccompanion.service`. This also restores
the earlier private address; it does not alter public SSH or Mihomo routing.

To stop the integration without removing data, disable `cccompanion.service`
and restore `/home/cc/.claude/settings.json.bak.cccompanion-20260927`.
Do not delete `/home/cc/.ots/secret` unless intentionally resetting the app
connection.
