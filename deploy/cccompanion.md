# CcCompanion server deployment

The upstream checkout lives at `/home/cc/CcCompanion`. Its Python environment is
`/home/cc/CcCompanion/apns-server/.venv`. The server runs as `cc` through
`cccompanion.service` and connects to the `CcCompanion` tmux session.

The server listens on `127.0.0.1:8795` only. The existing Cloudflare Tunnel
routes `*.41297.site` to local Nginx on port 80; it was not changed for this
deployment. Install `ccc.41297.site.nginx.conf` at
`/etc/nginx/conf.d/ccc.41297.site.conf`. Only local cloudflared connections may
reach this virtual host. An Nginx `auth_request` checks every request against
the server's `/tokens` endpoint before forwarding it, including `/health`.
The TestFlight app sends its existing `X-Auth-Token` header; an unauthenticated
public request must receive HTTP 401. No Tailscale connection is needed on the
iPhone. The server's Tailscale and Mihomo services are otherwise unchanged.

Install `cccompanion-config.toml` as
`/home/cc/CcCompanion/apns-server/config.toml` with owner `cc` and mode 0600.
The server's existing shared secret remains at `/home/cc/.ots/secret` with mode
0600. Neither the secret nor APNs credentials belong in Git.

Merge the CcCompanion Stop hook from `claude-session-settings.json` into the
live `/home/cc/.claude/settings.json`; do not replace the entire live file.
The hook posts replies to the loopback server URL. The iPhone endpoint URL is
`https://ccc.41297.site`, with the existing shared secret.

Health checks:

```sh
systemctl status cccompanion cloudflared nginx
sudo -u cc tmux list-sessions
curl http://127.0.0.1:8795/health
curl -o /dev/null -w '%{http_code}\n' https://ccc.41297.site/health
```

The unauthenticated HTTPS check should print `401`; the app's authenticated
health check should return 200. Confirm chat send and reply with the iPhone's
Tailscale connection off. APNs push is disabled until valid Apple credentials
are configured; chat polling works without them.

Pre-change backups are at
`/home/cc/CcCompanion/apns-server/config.toml.bak.cloudflared-20260927` and
`/home/cc/.claude/settings.json.bak.cloudflared-20260927`. To restore the
previous Tailscale-only setup, restore those two files, remove the new Nginx
virtual host, test and reload Nginx, then restart `cccompanion.service`.
The previous private endpoint was `http://100.68.76.100:8795`.
