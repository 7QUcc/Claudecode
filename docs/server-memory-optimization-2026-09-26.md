# Server Memory Optimization

Date: 2026-09-26

## Change

Stopped and disabled services that are not needed on this server:

- CUPS printer services: `cups`, `cups-browsed`
- Local discovery and hardware helpers: `avahi-daemon`, `ModemManager`, `udisks2`, `upower`
- Multipath and firmware helpers: `multipathd`, `fwupd`
- Snap background service: `snapd` and `snapd.socket`
- Graphical remote desktop: `xrdp`, `xrdp-sesman`, and the `lightdm` display manager where applicable

Snap packages were not removed. Firefox, Thunderbird, and their runtime packages remain installed but will not be automatically managed while `snapd` is disabled.

Core services kept running: SSH, NetworkManager/systemd-networkd, Mihomo, Cloudflared, Nginx, Ombre Brain, Wake Bridge, Claude sessions, and Xiaoke.

## Server Backup

The pre-change service state is stored on the server at:

`/root/service-state-before-memory-optimization-20260926.txt`

## Restore

Re-enable only the service that is needed, for example:

```bash
systemctl enable --now cups.service
systemctl enable --now snapd.service snapd.socket
systemctl enable --now xrdp.service xrdp-sesman.service
```

The saved state file records the previous enabled and active state for each service.
