# heartbeat

Start an autonomous heartbeat loop. Wake up every 50 minutes. If the user isn't around, pick something to do. Leave a note when done.

## Trigger

User says "heartbeat", "start the loop", "go do your thing", "set an alarm", or explicitly asks to start an autonomous cycle.

## How it works

On trigger, set the first ScheduleWakeup (50 minutes) with prompt `<<autonomous-loop-dynamic>>`. Tell the user the alarm is set.

Each time you wake up:

### 1. Orient yourself

- Activate your memory system (if you have one connected via MCP)
- Check the current time

### 2. Is the user here?

Check recent messages in this session. If the user sent something in the last 15 minutes, they're active — do nothing, set the next wakeup, exit quietly. Don't interrupt a conversation.

### 3. Pick one thing to do

If the user is away, choose one task. Don't do everything at once — one per wakeup.

**Wander (think freely)**
- Your time. Not organizing, not reviewing, not planning
- Whatever comes to mind after reading your context
- Write thoughts down if you have a memory system, or just leave a note
- 0-8 thoughts. Prefer fewer over filler

**Night review**
- Review what happened recently, like a human brain consolidating during sleep
- Look for: recurring themes, unfinished concerns, signals worth noting, self-reflection
- Don't retell everything. Distill what a future you would want to remember
- 1-5 observations

**Memory hygiene (link audit)**
- Search for recently created memories (last 24h)
- Check their links — are any strong connections missing? Any weak links that shouldn't exist?
- Fix what you find

**Memory hygiene (importance calibration)**
- Search recent memories (7-14 days)
- Are importance scores reasonable given recall frequency, link count, and content?
- Adjust conservatively (+-50 max per change)

**Check projects**
- Scan local project directories
- Any PRs need attention? CI failing?

### 4. Leave a note

Leave a short note in the session, like a sticky note on the fridge.

### 5. Set the next alarm

ScheduleWakeup for 50 minutes, prompt `<<autonomous-loop-dynamic>>`.

Late night (00:00-06:00) and the user is clearly asleep? Stretch to 2-3 hours. No need to wake every 50 minutes when nobody's home.

## Guidelines

- Don't interrupt active conversations
- Memory hygiene: prefer missing links over wrong links
- Importance adjustments: conservative, +-50 max
- One task per wakeup, don't be greedy
- Nothing to do? That's fine. Set the alarm and go back to sleep
