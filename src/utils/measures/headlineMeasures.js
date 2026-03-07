/**
 * Headline page measures — computes all metrics for the Share Through Renewal
 * headline story: pre/post share, shopping rate, retention, competitive exchange,
 * premium change comparison, channel comparison, net movement rank, and deep-dive breakdowns.
 */
import { THRESHOLDS } from '../brandConstants';

const NEUTRAL_GAP_THRESHOLD = 1.0; // percentage points
const MIN_N = THRESHOLDS.indicative; // 30 — minimum sample for deep-dive breakdowns

const PRICE_DIRECTIONS = ['Up', 'Unchanged', 'Down'];
const PRICE_LABELS = { Up: 'Higher', Unchanged: 'Unchanged', Down: 'Lower' };

function _pct(n, d) {
  return d > 0 ? n / d : 0;
}

/**
 * Core headline metrics for an insurer vs market.
 */
export function calcHeadlineMetrics(data, insurer) {
  if (!data?.length || !insurer) return null;
  const total = data.length;

  const existing = data.filter(r => r.Switchers !== 'New-to-market');
  const newToMarket = data.filter(r => r.Switchers === 'New-to-market');
  const shoppers = existing.filter(r => r.Shoppers === 'Shoppers');
  const nonShoppers = existing.filter(r => r.Shoppers !== 'Shoppers');
  const shopStay = shoppers.filter(r => r.Switchers === 'Non-switcher');
  const shopSwitch = shoppers.filter(r => r.Switchers === 'Switcher');

  const mktShopPct = _pct(shoppers.length, existing.length);
  const mktNewBizPct = _pct(newToMarket.length, total);
  const mktShopStayPct = _pct(shopStay.length, shoppers.length);
  const mktRetainedPct = _pct(nonShoppers.length + shopStay.length, total);

  const insExisting = existing.filter(r => r.PreRenewalCompany === insurer);
  const insNewBiz = newToMarket.filter(r => r.CurrentCompany === insurer);
  const insNonShop = insExisting.filter(r => r.Shoppers !== 'Shoppers');
  const insShoppers = insExisting.filter(r => r.Shoppers === 'Shoppers');
  const insShopStay = insShoppers.filter(r => r.Switchers === 'Non-switcher');
  const insShopSwitch = insShoppers.filter(r => r.Switchers === 'Switcher');
  const insTotal = insExisting.length + insNewBiz.length;
  const insRetained = insNonShop.length + insShopStay.length;

  const preShare = _pct(insExisting.length, total);
  const afterCount = data.filter(r => r.CurrentCompany === insurer).length;
  const afterShare = _pct(afterCount, total);

  // Won from (top 3)
  const switchersTo = data.filter(
    r => r.Switchers === 'Switcher' && r.CurrentCompany === insurer && r.PreRenewalCompany !== insurer
  );
  const totalWon = switchersTo.length + insNewBiz.length;
  const wonCounts = {};
  switchersTo.forEach(r => {
    const b = r.PreRenewalCompany || 'Other';
    wonCounts[b] = (wonCounts[b] || 0) + 1;
  });
  if (insNewBiz.length > 0) wonCounts['New to market'] = insNewBiz.length;
  const wonFrom = Object.entries(wonCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([brand, count]) => ({ brand, pct: totalWon > 0 ? count / totalWon : 0 }));

  // Lost to (top 3)
  const lostSwitchers = data.filter(
    r => r.Switchers === 'Switcher' && r.PreRenewalCompany === insurer
  );
  const totalLost = lostSwitchers.length;
  const lostCounts = {};
  lostSwitchers.forEach(r => {
    const b = r.CurrentCompany || 'Other';
    lostCounts[b] = (lostCounts[b] || 0) + 1;
  });
  const lostTo = Object.entries(lostCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([brand, count]) => ({ brand, pct: totalLost > 0 ? count / totalLost : 0 }));

  return {
    insurer,
    preShare,
    afterShare,
    shareDelta: afterShare - preShare,
    shopPct: _pct(insShoppers.length, insExisting.length),
    mktShopPct,
    retainedPct: _pct(insRetained, insTotal),
    mktRetainedPct,
    shopStayPct: _pct(insShopStay.length, insShoppers.length),
    mktShopStayPct,
    shopSwitchPct: _pct(insShopSwitch.length, insShoppers.length),
    mktShopSwitchPct: _pct(shopSwitch.length, shoppers.length),
    newBizPct: _pct(insNewBiz.length, insTotal),
    mktNewBizPct,
    wonFrom,
    lostTo,
    n: total,
  };
}

/**
 * Derive insight tag: "Ahead", "Below", or "In line".
 */
export function deriveTag(insVal, mktVal) {
  const gapPp = (insVal - mktVal) * 100;
  if (Math.abs(gapPp) < NEUTRAL_GAP_THRESHOLD) return 'In line';
  return gapPp > 0 ? 'Ahead' : 'Below';
}

/**
 * Premium change comparison: insurer vs market (excludes new-to-market).
 */
export function calcPremiumChangeComparison(data, insurer) {
  if (!data?.length || !insurer) return null;
  const existing = data.filter(r => r.Switchers !== 'New-to-market');
  const insRows = existing.filter(r => r.PreRenewalCompany === insurer);
  if (insRows.length === 0) return null;

  function split(subset) {
    const n = subset.length;
    if (n === 0) return { higher: 0, unchanged: 0, lower: 0 };
    const higher = subset.filter(r => r.price_direction === 'Up').length;
    const unchanged = subset.filter(r => r.price_direction === 'Unchanged').length;
    const lower = subset.filter(r => r.price_direction === 'Down').length;
    return { higher: higher / n, unchanged: unchanged / n, lower: lower / n };
  }

  return { insurer: split(insRows), market: split(existing) };
}

/**
 * Channel comparison: PCW vs Direct/Other for shoppers, insurer vs market.
 */
export function calcChannelComparison(data, insurer) {
  if (!data?.length || !insurer) return null;
  const existing = data.filter(r => r.Switchers !== 'New-to-market');
  const shoppers = existing.filter(r => r.Shoppers === 'Shoppers');
  const insShoppers = shoppers.filter(r => r.PreRenewalCompany === insurer);
  if (insShoppers.length === 0 || shoppers.length === 0) return null;

  function split(subset) {
    const n = subset.length;
    if (n === 0) return { pcw: 0, direct: 0 };
    const pcw = subset.filter(r => r.is_pcw_user).length;
    return { pcw: pcw / n, direct: (n - pcw) / n };
  }

  return { insurer: split(insShoppers), market: split(shoppers) };
}

/**
 * Rank insurer by net movement among all brands.
 * Uses single-pass counting instead of per-brand filtering.
 */
export function calcNetMovementRank(data, insurer) {
  if (!data?.length || !insurer) return null;
  const total = data.length;

  // Single pass: count pre and post occurrences per brand
  const preCount = {};
  const postCount = {};
  data.forEach(r => {
    if (r.PreRenewalCompany) preCount[r.PreRenewalCompany] = (preCount[r.PreRenewalCompany] || 0) + 1;
    if (r.CurrentCompany) postCount[r.CurrentCompany] = (postCount[r.CurrentCompany] || 0) + 1;
  });

  const allBrands = new Set([...Object.keys(preCount), ...Object.keys(postCount)]);
  const movements = [...allBrands]
    .map(brand => ({ brand, delta: ((postCount[brand] || 0) - (preCount[brand] || 0)) / total }))
    .sort((a, b) => b.delta - a.delta);

  const idx = movements.findIndex(m => m.brand === insurer);
  if (idx === -1) return null;

  return {
    rank: idx + 1,
    totalBrands: movements.length,
    insurerDelta: movements[idx].delta,
  };
}

// ---------------------------------------------------------------------------
// Deep-dive helpers — consolidated to avoid redundant filtering
// ---------------------------------------------------------------------------

/**
 * Pre-filter data into reusable segments for all deep-dive functions.
 */
function _prepareSegments(data, insurer) {
  const existing = data.filter(r => r.Switchers !== 'New-to-market');
  const insExisting = existing.filter(r => r.PreRenewalCompany === insurer);
  const shoppers = existing.filter(r => r.Shoppers === 'Shoppers');
  const insShopStay = shoppers.filter(r => r.PreRenewalCompany === insurer && r.Switchers === 'Non-switcher');
  const mktShopStay = shoppers.filter(r => r.Switchers === 'Non-switcher');
  return { existing, insExisting, shoppers, insShopStay, mktShopStay };
}

/**
 * Generic rate-by-group: for each group value, compute rate of conditionFn.
 */
function _rateByGroup(insSubset, mktSubset, groupField, conditionFn) {
  const groups = [...new Set(mktSubset.map(r => r[groupField]).filter(Boolean))].sort();
  return groups.map(g => {
    const insGrp = insSubset.filter(r => r[groupField] === g);
    const mktGrp = mktSubset.filter(r => r[groupField] === g);
    return {
      label: g,
      insurer: insGrp.length >= MIN_N ? _pct(insGrp.filter(conditionFn).length, insGrp.length) : null,
      market: mktGrp.length >= MIN_N ? _pct(mktGrp.filter(conditionFn).length, mktGrp.length) : null,
      insN: insGrp.length,
      mktN: mktGrp.length,
    };
  });
}

/**
 * Rate by premium change direction, with display labels.
 */
function _rateByPremiumChange(insSubset, mktSubset, conditionFn) {
  return PRICE_DIRECTIONS.map(dir => {
    const insGrp = insSubset.filter(r => r.price_direction === dir);
    const mktGrp = mktSubset.filter(r => r.price_direction === dir);
    return {
      label: PRICE_LABELS[dir],
      insurer: insGrp.length >= MIN_N ? _pct(insGrp.filter(conditionFn).length, insGrp.length) : null,
      market: mktGrp.length >= MIN_N ? _pct(mktGrp.filter(conditionFn).length, mktGrp.length) : null,
      insN: insGrp.length,
      mktN: mktGrp.length,
    };
  });
}

export function shoppingRateByPremiumChange(data, insurer) {
  const { existing, insExisting } = _prepareSegments(data, insurer);
  return _rateByPremiumChange(insExisting, existing, r => r.Shoppers === 'Shoppers');
}

export function retentionByPremiumChange(data, insurer) {
  const { existing, insExisting } = _prepareSegments(data, insurer);
  return _rateByPremiumChange(insExisting, existing, r => r.Switchers === 'Non-switcher');
}

export function shoppingRateByAge(data, insurer) {
  const { existing, insExisting } = _prepareSegments(data, insurer);
  return _rateByGroup(insExisting, existing, 'Age Group', r => r.Shoppers === 'Shoppers');
}

export function retentionByRegion(data, insurer) {
  const { existing, insExisting } = _prepareSegments(data, insurer);
  return _rateByGroup(insExisting, existing, 'Region', r => r.Switchers === 'Non-switcher');
}

export function shopStayByPremiumChange(data, insurer) {
  const { insShopStay, mktShopStay } = _prepareSegments(data, insurer);
  return PRICE_DIRECTIONS.map(dir => ({
    label: PRICE_LABELS[dir],
    insurer: insShopStay.length > 0 ? _pct(insShopStay.filter(r => r.price_direction === dir).length, insShopStay.length) : 0,
    market: mktShopStay.length > 0 ? _pct(mktShopStay.filter(r => r.price_direction === dir).length, mktShopStay.length) : 0,
  }));
}

export function shopStayPCWUsage(data, insurer) {
  const { insShopStay, mktShopStay } = _prepareSegments(data, insurer);
  if (insShopStay.length < MIN_N) return null;
  return {
    insurer: _pct(insShopStay.filter(r => r.is_pcw_user).length, insShopStay.length),
    market: mktShopStay.length > 0 ? _pct(mktShopStay.filter(r => r.is_pcw_user).length, mktShopStay.length) : 0,
  };
}

export function newBizSourceBrands(data, insurer) {
  const switchersTo = data.filter(
    r => r.Switchers === 'Switcher' && r.CurrentCompany === insurer && r.PreRenewalCompany !== insurer
  );
  const newBiz = data.filter(r => r.Switchers === 'New-to-market' && r.CurrentCompany === insurer);
  const totalWon = switchersTo.length + newBiz.length;
  const counts = {};
  switchersTo.forEach(r => {
    const b = r.PreRenewalCompany || 'Other';
    counts[b] = (counts[b] || 0) + 1;
  });
  if (newBiz.length > 0) counts['New to market'] = newBiz.length;
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([brand, count]) => ({ brand, pct: totalWon > 0 ? count / totalWon : 0 }));
}

export function newBizChannelBreakdown(data, insurer) {
  const switchersTo = data.filter(
    r => r.Switchers === 'Switcher' && r.CurrentCompany === insurer && r.PreRenewalCompany !== insurer
  );
  const allSwitchers = data.filter(r => r.Switchers === 'Switcher');
  if (switchersTo.length < MIN_N) return null;
  return {
    insurer: _pct(switchersTo.filter(r => r.is_pcw_user).length, switchersTo.length),
    market: allSwitchers.length > 0 ? _pct(allSwitchers.filter(r => r.is_pcw_user).length, allSwitchers.length) : 0,
  };
}
