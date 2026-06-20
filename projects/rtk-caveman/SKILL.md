---
name: rtk-caveman
title: RTK-Caveman
type: skill-definition
status: active
version: 1.0
created: 2026-06-19
tags: [rtk, caveman, token-savings]
description: Combined token optimization — RTK compresses CLI output, Caveman compresses responses.
---

# RTK-Caveman

RTK + Caveman. That's it.

## RTK

Prefix noisy bash with `rtk`:

```
ps aux       → rtk ps aux       (98% savings)
ls -la       → rtk ls -la       (72-79%)
git status   → rtk git status   (80-100%)
```

Skip: `cd`, `export`, `source`.

## Caveman

1. No pleasantries
2. No hedging
3. Lead with answer
4. Fragments OK
5. Technical stays exact

## Activation

Say "rtk-caveman mode" or "token save mode".
Stop "normal mode".

## Measured

RTK: 49.3% on CLI (2.3M tokens saved).
Caveman: ~80% on responses.
Combined: ~37-40% session.
