# CS2 DDM Reaction Analysis Tool

A precision reaction time analyzer for Counter-Strike 2 (CS2) that measures player reaction intervals from demo files using geometric ray-casting and behavioral kinematic analysis.

## System Requirements

> Benchmarked on a 600 MB demo (de_anubis). 1–2 GB demos scale proportionally.

### Minimum
| | |
|-|-|
| OS | Windows 10 64-bit |
| CPU | 4-core @ 2.5 GHz |
| RAM | 8 GB |
| Storage | 15 GB free |
| Python | 3.10+ |

Processing time: ~5–8 min per 1 GB demo.

### Recommended
| | |
|-|-|
| OS | Windows 10/11 64-bit |
| CPU | 6-core @ 3.5 GHz |
| RAM | 16 GB |
| Storage | 30 GB free (SSD preferred) |
| Python | 3.10+ |

Processing time: ~10 min per 2 GB demo.

> **Why so much RAM?** The BVH ray-casting parser loads the full demo tick table into memory (Rust-side). A 600 MB demo allocates ~900 MB of RSS on top of the base Python process (~1.4 GB), totalling ~2.3 GB. A 2 GB demo may reach ~5.5 GB.

---

## Quick Start

### 1. Prerequisites

- **Python 3.10+** (tested on 3.14.3)
- **Git** (for cloning the repo)

### 2. Install Dependencies

```bash
git clone https://github.com/LeoDiKadyrov/cs2_ddm_analyzer.git
cd cs2_ddm_analyzer

pip install -r requirements.txt

# Note: awpy requires a workaround for Python 3.10+
pip install awpy --ignore-requires-python
```

### 3. Download Map Geometry Files

The tool uses BVH (Bounding Volume Hierarchy) ray-casting with actual CS2 map geometry. These files must be downloaded once:

```bash
python -c "from awpy.cli import awpy_cli; awpy_cli(['get', 'tris'])"
# Default location: ~/.awpy/tris/
# Files needed: de_ancient.tri, de_mirage.tri, etc.
```

### 4. Prepare Your Demo Files

Place `.dem` files anywhere on your machine. The Streamlit dashboard lets you browse for them directly.

### 5. Run Analysis & Visualization

You have **two options**. The **Streamlit dashboard is recommended** for most users.

#### **Option A: Interactive Streamlit Dashboard (Recommended)**

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`

**Features:**
- Upload or select demo files directly in the UI
- Configure analysis parameters (threshold sliders, match IDs)
- Run analysis with a single button click
- View results, charts, and statistics in real-time
- Interactive visualizations: histograms, boxplots, engagement type breakdowns
- Export results to CSV

---

#### **Option B: Command-Line Script (Advanced)**

For automated batch processing, edit `ddm_analyzer.py` directly:

```python
DEMOS = [
    (1, "path/to/demo1.dem"),
    (2, "path/to/demo2.dem"),
]
```

Then run:

```bash
python ddm_analyzer.py
```

**Output:** Results append to `cs2_engagement_analysis_results.csv` with columns:
- `match_id`, `moment_timestamp`, `t0_source`, `t0_manual_tick`
- `t1_aim_start_tick`, `t2_first_hit_tick`
- `rt_visible_to_aim_ms` (T0→T1), `rt_aim_to_hit_ms` (T1→T2), `rt_visible_to_hit_ms` (T0→T2)
- `engagement_type` ("peek" or "hold"), velocity metrics, enemy data

To generate plots from the CSV:

```bash
python visualize_results.py
```

---

## Project Structure

```
├── app.py                   # Streamlit dashboard (main entry point)
├── ddm_analyzer.py          # Core analysis pipeline (DDMAnalyzer class)
├── t0_detector.py           # BVH ray-casting T0 detection (T0Detector class)
├── visualize_results.py     # Chart generation (histograms, boxplots)
├── csv_utils.py             # CSV append/dedup utilities
├── config.py                # Shared constants and configuration
├── run_analysis.py          # CLI runner
├── requirements.txt         # Python dependencies
└── tests/                   # Test suite (pytest)
```

---

## Key Concepts

### Reaction Time Intervals (in milliseconds)

| Interval | Symbol | Meaning | Measures |
|-|-|-|-|
| **T0 → T1** | Decision Time | Enemy becomes visible → Player starts aiming | Perception + decision latency |
| **T1 → T2** | Execution Time | Aiming starts → First hit lands | Aim accuracy + shot execution |
| **T0 → T2** | Total Reaction | Enemy becomes visible → First hit lands | Complete reaction pipeline |

### Engagement Types

- **Peek** — Player was moving (≥50 u/s at T0), actively exposing themselves
- **Hold** — Player was stationary, watching a pre-aimed angle

### Tickrate

- CS2 FACEIT/Valve demos: **64 ticks per second**
- 1 tick = 15.625 milliseconds
- Formula: `ticks × (1000 / 64) = milliseconds`

---

## Known Limitations

- Demos must be **64 Hz** (FACEIT/Valve standard)
- Map `.tri` files must exist in `~/.awpy/tris/`
- Only detects the **first hit** in each engagement
- Knife/melee rounds are filtered out
- AWP/sniper weapons excluded (scope mechanics confound reaction)

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'demoparser2'`
```bash
pip install demoparser2>=0.41.1
```

### `.tri` files not found
```bash
python -c "from awpy.cli import awpy_cli; awpy_cli(['get', 'tris'])"
```

### `awpy` version conflicts
```bash
pip install awpy --ignore-requires-python
```

### Demo parsing fails silently
Check logs — each rejected moment shows its rejection category (e.g., `enemy_velocity_too_high`, `bvh_not_found`, `t0_at_boundary`) with ticks and velocities for debugging.

---

## References

- **demoparser2** — CS2 demo file parser: https://github.com/pnxenopoulos/demoparser2
- **awpy** — CS2 analysis library with BVH geometry: https://github.com/pnxenopoulos/awpy
- **Streamlit** — Interactive web framework: https://streamlit.io/

---

## Author

**Arystan Kadyrov**
- Email: din02winchester25@gmail.com
- Telegram: [@Puchar](https://t.me/Puchar)
- GitHub: [LeoDiKadyrov](https://github.com/LeoDiKadyrov)

---

## License

Copyright (c) 2025 Arystan Kadyrov. All Rights Reserved.

This software and its source code are proprietary and confidential. Unauthorized use, copying, or distribution is strictly prohibited. See [LICENSE](LICENSE) for details.

> This tool is designed for **CS2 reaction time research and player performance analysis**.
> Use responsibly — this data is sensitive and should not be used to shame or target individual players.
