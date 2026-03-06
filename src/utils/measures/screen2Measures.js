import { filterByInsurer } from './shared';

/**
 * Shopping rate: proportion who shopped around.
 */
export function shoppingRate(data, insurer) {
  const filtered = filterByInsurer(data, insurer);
  if (filtered.length === 0) return null;
  const shoppers = filtered.filter(r => r.Shoppers === 'Shoppers').length;
  return shoppers / filtered.length;
}

/**
 * Non-shopping rate: proportion who did not shop.
 */
export function nonShoppingRate(data, insurer) {
  const filtered = filterByInsurer(data, insurer);
  if (filtered.length === 0) return null;
  const nonShoppers = filtered.filter(r => r.Shoppers === 'Non-shoppers').length;
  return nonShoppers / filtered.length;
}

/**
 * Shopping rate by month.
 * Returns array of { month, monthDisplay, rate, n, shopperCount }.
 */
export function shoppingRateByMonth(data, insurer) {
  const filtered = filterByInsurer(data, insurer);
  const grouped = {};

  filtered.forEach(row => {
    const m = row.RenewalYearMonth;
    if (!grouped[m]) grouped[m] = { total: 0, shoppers: 0, display: row.RenewalMonthDisplay };
    grouped[m].total++;
    if (row.Shoppers === 'Shoppers') grouped[m].shoppers++;
  });

  return Object.entries(grouped)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([month, g]) => ({
      month: Number(month),
      monthDisplay: g.display,
      rate: g.total > 0 ? g.shoppers / g.total : 0,
      n: g.total,
      shopperCount: g.shoppers,
    }));
}

/**
 * PCW usage rate among shoppers.
 * Only counts rows where Shoppers = "Shoppers".
 */
export function pcwUsageRate(data, insurer) {
  const filtered = filterByInsurer(data, insurer);
  const shoppers = filtered.filter(r => r.Shoppers === 'Shoppers');
  if (shoppers.length === 0) return null;
  const usedPCW = shoppers.filter(r => r['Did you use a PCW for shopping'] === 'Yes').length;
  return usedPCW / shoppers.length;
}

/**
 * Trend change: split the time range into two equal halves.
 * Returns { recentRate, previousRate, changePts, recentN, previousN } or null.
 *
 * Only valid if both halves have n >= 30 (checked by caller via governance).
 */
export function trendChange(data, insurer) {
  const filtered = filterByInsurer(data, insurer);
  const months = [...new Set(filtered.map(r => r.RenewalYearMonth))].sort((a, b) => a - b);

  if (months.length < 2) return null;

  const midpoint = Math.floor(months.length / 2);
  const previousMonths = new Set(months.slice(0, midpoint));
  const recentMonths = new Set(months.slice(midpoint));

  const previousRows = filtered.filter(r => previousMonths.has(r.RenewalYearMonth));
  const recentRows = filtered.filter(r => recentMonths.has(r.RenewalYearMonth));

  if (previousRows.length === 0 || recentRows.length === 0) return null;

  const previousRate = previousRows.filter(r => r.Shoppers === 'Shoppers').length / previousRows.length;
  const recentRate = recentRows.filter(r => r.Shoppers === 'Shoppers').length / recentRows.length;

  return {
    recentRate,
    previousRate,
    changePts: recentRate - previousRate,
    recentN: recentRows.length,
    previousN: previousRows.length,
  };
}

/**
 * Generate narrative text for insurer mode.
 * "[Insurer] customers shop at [X%], [N]pts [above/below] market average of [Y%]."
 */
export function generateNarrative(insurer, insurerRate, marketRate) {
  if (insurerRate === null || marketRate === null || !insurer) return null;

  const insurerPct = (insurerRate * 100).toFixed(1);
  const marketPct = (marketRate * 100).toFixed(1);
  const gapPts = ((insurerRate - marketRate) * 100).toFixed(1);
  const direction = insurerRate > marketRate ? 'above' : insurerRate < marketRate ? 'below' : 'in line with';
  const absGap = Math.abs(parseFloat(gapPts)).toFixed(1);

  if (direction === 'in line with') {
    return `${insurer} customers shop at ${insurerPct}%, in line with the market average of ${marketPct}%.`;
  }

  return `${insurer} customers shop at ${insurerPct}%, ${absGap}pts ${direction} the market average of ${marketPct}%.`;
}
