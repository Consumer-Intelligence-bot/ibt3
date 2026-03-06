/**
 * Why They Move measures (Screen 4).
 * Proxy reason data derived from main data when Q8/Q19/Q31 response data is unavailable.
 */

/**
 * Price direction split for a segment.
 */
function priceDirectionSplit(data) {
  const counts = { Up: 0, Down: 0, Unchanged: 0, New: 0 };
  data.forEach((r) => {
    const d = r.price_direction;
    if (d && Object.hasOwn(counts, d)) counts[d]++;
  });
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  if (total === 0) return [];
  const labels = {
    Up: 'Premium went up',
    Down: 'Premium went down',
    Unchanged: 'Premium unchanged',
    New: 'New purchase',
  };
  return Object.entries(counts)
    .filter(([, c]) => c > 0)
    .map(([k, c]) => ({ label: labels[k], market_pct: c / total, insurer_pct: c / total }))
    .sort((a, b) => b.market_pct - a.market_pct);
}

/**
 * Proxy: Why they shopped — price direction for shoppers.
 */
export function proxyReasonsForShopping(data) {
  const shoppers = data.filter((r) => r.Shoppers === 'Shoppers');
  if (shoppers.length < 10) return null;
  return priceDirectionSplit(shoppers);
}

/**
 * Proxy: Why they didn't shop — satisfaction/tenure for non-shoppers.
 */
export function proxyReasonsForNotShopping(data) {
  const nonShoppers = data.filter((r) => r.Shoppers === 'Non-shoppers');
  if (nonShoppers.length < 10) return null;
  const reasons = [];
  const sat = {};
  const tenure = {};
  nonShoppers.forEach((r) => {
    const s = r.Q47 || r['Overall satisfaction'] || 'Unknown';
    sat[s] = (sat[s] || 0) + 1;
    const t = r.tenure_band || r.Q21 || 'Unknown';
    tenure[t] = (tenure[t] || 0) + 1;
  });
  const total = nonShoppers.length;
  Object.entries(sat)
    .filter(([k]) => k !== 'Unknown')
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .forEach(([label, c]) => reasons.push({ label: `Satisfaction: ${label}`, market_pct: c / total, insurer_pct: c / total }));
  if (reasons.length === 0) {
    Object.entries(tenure)
      .filter(([k]) => k !== 'Unknown')
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .forEach(([label, c]) => reasons.push({ label: `Tenure: ${label}`, market_pct: c / total, insurer_pct: c / total }));
  }
  return reasons.length > 0 ? reasons : priceDirectionSplit(nonShoppers);
}

/**
 * Proxy: Why they switched — price direction for switchers.
 */
export function proxyReasonsForSwitching(data) {
  const switchers = data.filter((r) => r.Switchers === 'Switcher');
  if (switchers.length < 10) return null;
  return priceDirectionSplit(switchers);
}

/**
 * Segment counts for baseN display. Returns { market, insurer } for each segment.
 */
export function getSegmentCounts(data, insurer) {
  const shoppers = data.filter((r) => r.Shoppers === 'Shoppers');
  const switchers = data.filter((r) => r.Switchers === 'Switcher');
  const nonShoppers = data.filter((r) => r.Shoppers === 'Non-shoppers');

  const byInsurer = (arr) => (insurer ? arr.filter((r) => r.CurrentCompany === insurer).length : null);

  return {
    shopping: { market: shoppers.length, insurer: byInsurer(shoppers) },
    switching: { market: switchers.length, insurer: byInsurer(switchers) },
    'not-shopping': { market: nonShoppers.length, insurer: byInsurer(nonShoppers) },
  };
}
