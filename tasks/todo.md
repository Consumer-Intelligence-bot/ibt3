# Ehubot TODO

## COMPLETED: Unprompted Awareness UI/UX Fixes

### Fix 1: Taller charts + dynamic height
- [x] Increase stacked area chart height from 380 to 520
- [x] Increase bump chart base height from 380 to 500
- [x] Scale bump chart height dynamically with `max_rank` (300 + max_rank * 30, min 500)

### Fix 2: Better legends
- [x] Stacked area chart: direct on-chart labels at last data point (brand + share %), legend hidden
- [x] Bump chart: move legend to right side (vertical layout), one brand per row
- [x] Increase legend font from 10px to 11px on bump chart
- [x] Labels only shown when slice > 3% to avoid clutter

### Fix 3: Tighten margins / reduce white space
- [x] Reduce bottom margin from 80 to 50 on both charts
- [x] Move export footer annotation from `y=-0.15` to `y=-0.10` in `chart_export.py`
- [x] Reduce top margin from 60 to 40 on both charts
- [x] Right margin increased on stacked area (120px) and bump (140px) to accommodate labels/legend
