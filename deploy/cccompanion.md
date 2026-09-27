# CcCompanion server deployment

The upstream checkout lives at `/home/cc/CcCompanion`. Its Python environment is
`/home/cc/CcCompanion/apns-server/.venv`. The server runs as `cc` through
`cccompanion.service` and connects to the `CcCompanion` tmux session.

The service binds only the server's Tailscale address on port 8795. Tailscale is
configured with `--accept-routes=false --accept-dns=false` and no exit node.
`tailscaled-proxy.conf` sends Tailscale control traffic through the existing
local Mihomo SOCKS listener. It does not change Mihomo routing.

Install `cccompanion-config.toml` as
`/home/cc/CcCompanion/apns-server/config.toml` with owner `cc` and mode 0600.
The upstream server creates its shared secret at `/home/cc/.ots/secret` with
mode 0600. Neither the secret nor APNs credentials belong in Git.

`claude-session-settings.json` adds the upstream CcCompanion Stop hook alongside
the existing thinking hook. The Stop hook posts replies back to the private
server URL; it reads the shared secret from `/home/cc/.ots/secret`.

Health checks:

```sh
systemctl status cccompanion tailscaled
sudo -u cc tmux list-sessions
curl http://100.82.181.117:8795/health
ip -4 route get 1.1.1.1
```

The URL is a private Tailnet address, not a public endpoint. If Tailscale assigns
a different address, update both `cccompanion-config.toml` and the Stop hook URL
in `claude-session-settings.json`, then redeploy and restart the affected service
and Claude session. APNs push is disabled until valid Apple credentials are
configured; chat polling works without them.

To stop the integration without removing data, disable `cccompanion.service`
and restore the pre-hook `claude-session-settings.json` backup on the server.
Do not delete `/home/cc/.ots/secret` unless intentionally resetting the app
connection.
