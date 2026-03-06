/**
 * Market Pulse measures (Screen 1 per spec).
 * Shopping Rate, Switching Rate, Shop & Stay Rate, PCW Usage.
 */
import { filterByInsurer, excludeNewToMarket } from './shared';

/**
 * Shopping Rate: % where Shoppers = "Shoppers"
 */
export function shoppingRate(data, insurer) {
  const filtered = filterByInsurer(data, insurer);
  if (filtered.length === 0) return null;
  return filtered.filter((r) => r.Shoppers === 'Shoppers').length / filtered.length;
}

/**
 * Switching Rate: % where Switchers = "Switcher"
 */
export function switchingRate(data, insurer) {
  const filtered = filterByInsurer(data, insurer);
  if (filtered.length === 0) return null;
  return filtered.filter((r) => r.Switchers === 'Switcher').length / filtered.length;
}

/**
 * Shop & Stay Rate: % who shopped but did not switch
 */
export function shopAndStayRate(data, insurer) {
  const filtered = filterByInsurer(data, insurer);
  if (filtered.length === 0) return null;
  const count = filtered.filter(
    (r) => r.Shoppers === 'Shoppers' && r.Switchers === 'Non-switcher'
  ).length;
  return count / filtered.length;
}

/**
 * PCW Usage: % of shoppers who used a PCW
 */
export function pcwUsageRate(data, insurer) {
  const filtered = filterByInsurer(data, insurer);
  const shoppers = filtered.filter((r) => r.Shoppers === 'Shoppers');
  if (shoppers.length === 0) return null;
  const used = shoppers.filter((r) => r['Did you use a PCW for shopping'] === 'Yes').length;
  return used / shoppers.length;
}

/**
 * All four rates by month for trend chart and sparklines.
 * Returns array of { month, monthDisplay, shoppingRate, switchingRate, shopAndStayRate, pcwUsageRate, n }.
 */
export function ratesByMonth(data, insurer) {
  const filtered = filterByInsurer(data, insurer);
  const grouped = {};

  filtered.forEach((row) => {
    const m = row.RenewalYearMonth;
    if (!grouped[m])
      grouped[m] = {
        total: 0,
        shoppers: 0,
        switchers: 0,
        shopAndStay: 0,
        pcwUsers: 0,
        display: row.RenewalMonthDisplay,
      };
    grouped[m].total++;
    if (row.Shoppers === 'Shoppers') {
      grouped[m].shoppers++;
      if (row['Did you use a PCW for shopping'] === 'Yes') grouped[m].pcwUsers++;
    }
    if (row.Switchers === 'Switcher') grouped[m].switchers++;
    if (row.Shoppers === 'Shoppers' && row.Switchers === 'Non-switcher') grouped[m].shopAndStay++;
  });

  return Object.entries(grouped)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([month, g]) => ({
      month: Number(month),
      monthDisplay: g.display,
      shoppingRate: g.total > 0 ? g.shoppers / g.total : 0,
      switchingRate: g.total > 0 ? g.switchers / g.total : 0,
      shopAndStayRate: g.total > 0 ? g.shopAndStay / g.total : 0,
      pcwUsageRate: g.shoppers > 0 ? g.pcwUsers / g.shoppers : 0,
      n: g.total,
    }));
}

/**
 * Trend change (previous vs recent period) for delta indicator.
 */
export function trendChange(data, insurer, metric) {
  const months = ratesByMonth(data, insurer);
  if (months.length < 2) return null;
  const midpoint = Math.floor(months.length / 2);
  const previous = months.slice(0, midpoint);
  const recent = months.slice(midpoint);
  const prevRate =
    previous.reduce((s, m) => s + (m[metric] || 0), 0) / previous.length;
  const recRate = recent.reduce((s, m) => s + (m[metric] || 0), 0) / recent.length;
  const prevN = previous.reduce((s, m) => s + m.n, 0);
  const recN = recent.reduce((s, m) => s + m.n, 0);
  return {
    previousValue: prevRate,
    recentValue: recRate,
    changePts: recRate - prevRate,
    previousN: prevN,
    recentN: recN,
  };
}

/**
 * Price direction split (Higher / Unchanged / Lower). Excludes new-to-market.
 */
export function priceDirectionSplit(data, insurer) {
  const filtered = excludeNewToMarket(filterByInsurer(data, insurer));
  if (filtered.length === 0) return { higher: 0, unchanged: 0, lower: 0, n: 0 };
  const change = (r) =>
    r['Renewal premium change'] ?? r['Renewal premium change combined'] ?? '';
  const higher = filtered.filter((r) => {
    const c = String(change(r)).toLowerCase();
    return c.includes('higher') || c === 'up';
  }).length;
  const lower = filtered.filter((r) => {
    const c = String(change(r)).toLowerCase();
    return c.includes('lower') || c === 'down';
  }).length;
  const unchanged = filtered.filter((r) => {
    const c = String(change(r)).toLowerCase();
    return c.includes('unchanged');
  }).length;
  return {
    higher: higher / filtered.length,
    unchanged: unchanged / filtered.length,
    lower: lower / filtered.length,
    n: filtered.length,
  };
}
