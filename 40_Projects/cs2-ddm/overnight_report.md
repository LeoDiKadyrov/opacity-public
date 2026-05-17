# Overnight watcher report

**Started:** 2026-05-16 22:21:42

**Task:** wait for top-5 rebatch → SQL distribution check → if PASS auto-expand to top-10 → final check

---

## Phase 1 — wait for top-5 rebatch

Polling `rebatch_top5.log` every 60s for completion or failure marker.

**Top-5 rebatch finished at 2026-05-16 23:36:43: OK**

## Phase 2 — SQL distribution check (top-5)

### Top-5 metrics

```
n_total:             436
min_ms:              0.0
max_ms:              1328.125
n_at_125ms:          8 (1.8%)
n_pre_aimed (rt=0):  37
n_pre_aimed (flag):  37
n_sustained_aim:     399
n_none_sentinel:     0
```

Per-demo:

| Demo | N | min_ms | n_at_125 |
|-|-|-|-|
| mouz-vs-spirit-m2-mirage.dem | 112 | 0.0 | 3 |
| passion-ua-vs-faze-m2-nuke.dem | 86 | 0.0 | 1 |
| spirit-vs-the-mongolz-m2-ancient.dem | 89 | 0.0 | 1 |
| spirit-vs-the-mongolz-m2-mirage.dem | 75 | 0.0 | 1 |
| spirit-vs-vitality-m1-mirage.dem | 74 | 0.0 | 2 |

### Top-5 acceptance PASSED at 2026-05-16 23:36:43

Auto-expanding to top-10.

## Phase 3 — delete pre-fix rows for next-5 + run rebatch

Deleted 365 pre-fix engagement rows for next-5 demos.

Starting next-5 rebatch at 2026-05-16 23:36:43 (sequential, log: `rebatch_top10.log`)

Next-5 rebatch finished at 2026-05-17 01:01:11: OK

## Phase 4 — SQL distribution check (top-10)

### Top-10 metrics

```
n_total:             785
min_ms:              0.0
max_ms:              1328.125
n_at_125ms:          10 (1.3%)
n_pre_aimed (rt=0):  71
n_pre_aimed (flag):  71
n_sustained_aim:     714
n_none_sentinel:     0
```

Per-demo:

| Demo | N | min_ms | n_at_125 |
|-|-|-|-|
| faze-vs-pain-m1-nuke.dem | 77 | 0.0 | 1 |
| faze-vs-pain-m2-dust2.dem | 71 | 0.0 | 1 |
| mouz-vs-spirit-m2-mirage.dem | 112 | 0.0 | 3 |
| passion-ua-vs-faze-m1-anubis.dem | 63 | 0.0 | 0 |
| passion-ua-vs-faze-m2-nuke.dem | 86 | 0.0 | 1 |
| spirit-vs-the-mongolz-m1-nuke.dem | 67 | 0.0 | 0 |
| spirit-vs-the-mongolz-m2-ancient.dem | 89 | 0.0 | 1 |
| spirit-vs-the-mongolz-m2-mirage.dem | 75 | 0.0 | 1 |
| spirit-vs-virtus-pro-m1-ancient.dem | 71 | 0.0 | 0 |
| spirit-vs-vitality-m1-mirage.dem | 74 | 0.0 | 2 |

## ALL CLEAR — top-10 acceptance PASSED at 2026-05-17 01:01:11

Next user action: review report, decide whether to expand to full corpus (~73 more demos). Recommended: spawn /gsd-execute style task or run third batch driver if confidence high.
