import { filterByInsurer, excludeNewToMarket } from './shared';

/**
 * Total renewals count.
 * Uses ALL rows (including new-to-market) for the headline count.
 */
export function totalRenewals(data, insurer) {
  return filterByInsurer(data, insurer).length;
}

/**
 * Percentage who saw a price increase.
 * Excludes new-to-market.
 */
export function priceUpPct(data, insurer) {
  const filtered = excludeNewToMarket(filterByInsurer(data, insurer));
  if (filtered.length === 0) return null;
  const up = filtered.filter(r => r['Renewal premium change'] === 'Higher').length;
  return up / filtered.length;
}

/**
 * Percentage who saw a price decrease.
 * Excludes new-to-market.
 */
export function priceDownPct(data, insurer) {
  const filtered = excludeNewToMarket(filterByInsurer(data, insurer));
  if (filtered.length === 0) return null;
  const down = filtered.filter(r => r['Renewal premium change'] === 'Lower').length;
  return down / filtered.length;
}

/**
 * Percentage whose price was unchanged.
 * Excludes new-to-market.
 */
export function priceUnchangedPct(data, insurer) {
  const filtered = excludeNewToMarket(filterByInsurer(data, insurer));
  if (filtered.length === 0) return null;
  const unchanged = filtered.filter(r => r['Renewal premium change'] === 'It was unchanged').length;
  return unchanged / filtered.length;
}

/**
 * Price change by month.
 * Returns array of { month, monthDisplay, upPct, downPct, unchangedPct, n }.
 * Excludes new-to-market.
 */
export function priceChangeByMonth(data, insurer) {
  const filtered = excludeNewToMarket(filterByInsurer(data, insurer));
  const grouped = {};
  filtered.forEach(row => {
    const m = row.RenewalYearMonth;
    if (!grouped[m]) grouped[m] = { total: 0, up: 0, down: 0, unchanged: 0, display: row.RenewalMonthDisplay };
    grouped[m].total++;
    if (row['Renewal premium change'] === 'Higher') grouped[m].up++;
    if (row['Renewal premium change'] === 'Lower') grouped[m].down++;
    if (row['Renewal premium change'] === 'It was unchanged') grouped[m].unchanged++;
  });
  return Object.entries(grouped)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([month, g]) => ({
      month: Number(month),
      monthDisplay: g.display,
      upPct: g.total > 0 ? g.up / g.total : 0,
      downPct: g.total > 0 ? g.down / g.total : 0,
      unchangedPct: g.total > 0 ? g.unchanged / g.total : 0,
      n: g.total,
    }));
}

/**
 * Price change band distribution.
 * direction: "up" or "down"
 * Returns array of { band, count, pct }, sorted by SortOrder.
 */
export function priceChangeBands(data, direction, insurer) {
  const filtered = filterByInsurer(data, insurer);
  let subset;
  let bandField;
  if (direction === 'up') {
    subset = filtered.filter(r => r['Renewal premium change'] === 'Higher');
    bandField = 'How much higher';
  } else {
    subset = filtered.filter(r => r['Renewal premium change'] === 'Lower');
    bandField = 'How much lower';
  }
  if (subset.length === 0) return [];
  const bandCounts = {};
  const bandSortOrder = {};
  subset.forEach(row => {
    const band = row[bandField];
    if (!band) return;
    bandCounts[band] = (bandCounts[band] || 0) + 1;
    if (row.SortOrder !== null) bandSortOrder[band] = row.SortOrder;
  });
  const total = subset.length;
  return Object.entries(bandCounts)
    .map(([band, count]) => ({
      band,
      count,
      pct: count / total,
      sortOrder: bandSortOrder[band] || 999,
    }))
    .sort((a, b) => a.sortOrder - b.sortOrder);
}

/**
 * Average price change (from midpoint columns).
 * direction: "up" or "down"
 * Returns the mean in £, or null if no data.
 */
export function avgPriceChange(data, direction, insurer) {
  const filtered = filterByInsurer(data, insurer);
  const field = direction === 'up'
    ? 'SumRenewal_premium_higher_value'
    : 'SumRenewal_premium_lower_value';
  const values = filtered
    .map(r => r[field])
    .filter(v => v !== null && v !== undefined && !isNaN(v));
  if (values.length === 0) return null;
  return values.reduce((sum, v) => sum + v, 0) / values.length;
}
