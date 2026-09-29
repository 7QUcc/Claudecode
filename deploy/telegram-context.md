# Telegram context command

`/context` is handled by the existing Telegram channel, not forwarded to Claude.
Only an already-paired user in a private chat can use it. The command invokes
`telegram_context.py`, which reads the same latest-assistant usage data as the
Xiaoke frontend. It reports the latest model-call snapshot, not live tokens
while Claude is responding.

The patch targets the installed official Telegram plugin version 0.0.7 and
checks its original SHA-256 before changing anything. Run the installer as the
`cc` user:

```sh
bash /home/cc/xiaoke/deploy/install-telegram-context.sh
```

The installer saves `server.ts.before-xiaoke-context` beside the installed
plugin and then patches `server.ts`. Restart the Telegram-owning Claude session
with its existing session ID to load the new handler. Do not start another
`getUpdates` consumer for the same bot token.

To roll back, restore `server.ts` from that backup and rebuild the same Claude
session with its existing session ID. A plugin update may install a different
version; review and adapt the patch before applying it to that version.
