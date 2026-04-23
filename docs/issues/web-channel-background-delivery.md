# Web Channel Background Delivery

## Status

Resolved by the filesystem-backed web mailbox bridge.

## Problem

Background jobs can target `channel="web"`, but outbound delivery for cron and heartbeat flows goes through `ChannelManager`.
The websocket-based web chat runtime in `web/backend/backend/utils/web_chat.py` previously had no routable bridge from the gateway process.

## Evidence

- Cron job store can persist web targets, for example:
  - `payload.channel = "web"`
  - `payload.to = "<session-id>"`
- Runtime warning:
  - `Unknown channel: web`
- Channel discovery currently finds only built-in channel modules under `miniclaw/channels/`, and there is no `web.py`.

## Previous Consequence

Scheduled or background responses destined for web sessions are generated, but they are not routable through the current outbound path.

## Implemented Fix

- Added `miniclaw.channels.web.WebChannel` so the gateway can route outbound `channel="web"` messages.
- Added `miniclaw.web_events.WebEventMailbox` as a shared filesystem-backed mailbox between the gateway and launcher processes.
- Added websocket-side background polling so active web sessions receive queued cron and heartbeat messages.

## Constraint

Any fix must avoid introducing a second, divergent web-delivery path for normal interactive chat turns.
