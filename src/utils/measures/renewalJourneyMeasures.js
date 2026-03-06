/**
 * Renewal Journey measures (Screen 2 - Sankey diagram).
 * Builds nodes and links for Origin Brand → Engagement → Outcome → Destination.
 */

function filterByInsurer(data, insurer) {
  if (!insurer) return data;
  return data.filter((row) => row.CurrentCompany === insurer || row.PreRenewalCompany === insurer);
}

/**
 * Get engagement tier from row.
 * Tier 2: New to Market, Negotiated, Shopped, Did Not Shop
 */
function getEngagement(row) {
  if (row.Switchers === 'New-to-market') return 'New to Market';
  if (row.Shoppers === 'Shoppers' && row.Q34a === 'Yes') return 'Negotiated';
  if (row.Shoppers === 'Shoppers') return 'Shopped';
  if (row.Shoppers === 'Non-shoppers') return 'Did Not Shop';
  return 'Shopped'; // fallback
}

/**
 * Get outcome tier from row.
 */
function getOutcome(row) {
  if (row.Switchers === 'Switcher') return 'Switched';
  return 'Stayed';
}

/**
 * Get destination: CurrentCompany for switchers, "Renewed" for stayers.
 */
function getDestination(row) {
  if (row.Switchers === 'Switcher') return row.CurrentCompany || 'Other';
  return 'Renewed';
}

/**
 * Group brand into top-N or "Other".
 */
function groupBrand(brand, topBrands) {
  if (!brand) return 'Other';
  return topBrands.includes(brand) ? brand : 'Other';
}

/**
 * Build Sankey nodes and links for the renewal journey.
 * @param {Array} data - filtered rows
 * @param {string|null} insurer - selected insurer for focus mode
 * @param {number} topN - number of brands to show (rest as "Other")
 */
export function buildSankeyData(data, insurer, topN = 8) {
  const filtered = filterByInsurer(data, insurer);
  if (filtered.length === 0) return { nodes: [], links: [] };

  // Top N brands by PreRenewalCompany volume
  const originCounts = {};
  filtered.forEach((r) => {
    const b = r.PreRenewalCompany;
    if (b) originCounts[b] = (originCounts[b] || 0) + 1;
  });
  const topBrands = Object.entries(originCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, topN)
    .map(([b]) => b);

  // Same for destination brands (switchers)
  const destCounts = {};
  filtered.filter((r) => r.Switchers === 'Switcher').forEach((r) => {
    const b = r.CurrentCompany;
    if (b) destCounts[b] = (destCounts[b] || 0) + 1;
  });
  const topDestBrands = Object.entries(destCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, topN)
    .map(([b]) => b);

  // Aggregate flows: (origin, engagement, outcome, destination) -> count
  const flowCounts = {};
  filtered.forEach((row) => {
    const origin = groupBrand(row.PreRenewalCompany, topBrands);
    const engagement = getEngagement(row);
    const outcome = getOutcome(row);
    const dest = outcome === 'Switched' ? groupBrand(row.CurrentCompany, topDestBrands) : 'Renewed';
    const key = `${origin}|${engagement}|${outcome}|${dest}`;
    flowCounts[key] = (flowCounts[key] || 0) + 1;
  });

  // Build unique nodes with tier
  const nodeMap = new Map();
  const addNode = (name, tier) => {
    const id = `${tier}:${name}`;
    if (!nodeMap.has(id)) nodeMap.set(id, { id, name, tier });
  };

  Object.keys(flowCounts).forEach((key) => {
    const [origin, engagement, outcome, dest] = key.split('|');
    addNode(origin, 0);
    addNode(engagement, 1);
    addNode(outcome, 2);
    addNode(dest, 3);
  });

  const nodes = Array.from(nodeMap.values()).sort((a, b) => {
    if (a.tier !== b.tier) return a.tier - b.tier;
    return a.name.localeCompare(b.name);
  });
  const nodeById = new Map(nodes.map((n, i) => [n.id, { ...n, index: i }]));

  // Build links (only between adjacent tiers)
  const links = [];
  Object.entries(flowCounts).forEach(([key, value]) => {
    const [origin, engagement, outcome, dest] = key.split('|');
    const n0 = nodeById.get(`0:${origin}`);
    const n1 = nodeById.get(`1:${engagement}`);
    const n2 = nodeById.get(`2:${outcome}`);
    const n3 = nodeById.get(`3:${dest}`);
    if (n0 && n1) links.push({ source: n0.index, target: n1.index, value });
    if (n1 && n2) links.push({ source: n1.index, target: n2.index, value });
    if (n2 && n3) links.push({ source: n2.index, target: n3.index, value });
  });

  // Deduplicate links (same source-target can come from different flows)
  const linkMap = new Map();
  links.forEach((l) => {
    const k = `${l.source}-${l.target}`;
    linkMap.set(k, { ...l, value: (linkMap.get(k)?.value || 0) + l.value });
  });

  return {
    nodes: nodes.map(({ id, name, tier }) => ({ id, name, tier })),
    links: Array.from(linkMap.values()).map(({ source, target, value }) => ({ source, target, value })),
  };
}

/**
 * Derive channel breakdown from raw data or API.
 * Looks for QuoteChannel/PurchaseChannel columns, or uses PCW usage as fallback.
 * @param {Array} rows - filtered rows
 * @param {string} type - 'quote' (shoppers) | 'purchaseInto' (switchers to insurer) | 'purchaseFrom' (switchers from insurer)
 * @param {string|null} insurer - selected insurer
 * @param {Array|null} apiChannels - channel_usage from getChannels API { label, market_pct, insurer_pct }
 */
function buildChannelBreakdown(rows, type, insurer, apiChannels) {
  if (apiChannels?.length) {
    return apiChannels.map((c) => ({
      brand: c.label,
      pct: (insurer != null && c.insurer_pct != null ? c.insurer_pct : c.market_pct) ?? 0,
      marketPct: c.market_pct ?? 0,
    }));
  }
  // Fallback: derive from "Did you use a PCW for shopping"
  const col = 'Did you use a PCW for shopping';
  const base = type === 'quote' ? rows.filter((r) => r.Shoppers === 'Shoppers') : rows;
  if (!base.length) return [];
  const pcwYes = base.filter((r) => r[col] === 'Yes' || r[col] === true).length;
  const pcwNo = base.length - pcwYes;
  return [
    { brand: 'PCW', pct: pcwYes / base.length, marketPct: pcwYes / base.length },
    { brand: 'Direct / Other', pct: pcwNo / base.length, marketPct: pcwNo / base.length },
  ];
}

/**
 * Build Shopping Journey data (Admiral-style layout).
 * Before Renewal → Shoppers/Non Shoppers → Retained/Switched From → After Renewal.
 * Includes channel breakdowns for Quote Channel, Purchase into, Purchase from.
 */
export function buildShoppingJourneyData(data, insurer, channels = null) {
  if (!data?.length) return null;

  const total = data.length;
  const relevant = insurer
    ? data.filter((r) => r.PreRenewalCompany === insurer || r.CurrentCompany === insurer)
    : data;
  if (relevant.length === 0 && insurer) return null;

  const newToMarket = data.filter((r) => r.Switchers === 'New-to-market');
  const existing = data.filter((r) => r.Switchers !== 'New-to-market');
  const nonShoppers = existing.filter((r) => r.Shoppers === 'Non-shoppers');
  const shoppers = existing.filter((r) => r.Shoppers === 'Shoppers');
  const shopStay = shoppers.filter((r) => r.Switchers === 'Non-switcher');
  const shopSwitch = shoppers.filter((r) => r.Switchers === 'Switcher');

  const pct = (n, base) => (base > 0 ? n / base : 0);

  if (insurer) {
    const insurerExisting = existing.filter((r) => r.PreRenewalCompany === insurer);
    const insurerNewBiz = newToMarket.filter((r) => r.CurrentCompany === insurer);
    const insurerNonShop = insurerExisting.filter((r) => r.Shoppers === 'Non-shoppers');
    const insurerShoppers = insurerExisting.filter((r) => r.Shoppers === 'Shoppers');
    const insurerShopStay = insurerShoppers.filter((r) => r.Switchers === 'Non-switcher');
    const insurerShopSwitch = insurerShoppers.filter((r) => r.Switchers === 'Switcher');
    const retained = insurerNonShop.length + insurerShopStay.length;
    const switchedFrom = insurerShopSwitch.length;
    const switchedInto = insurerNewBiz.length + data.filter((r) => r.Switchers === 'Switcher' && r.CurrentCompany === insurer && r.PreRenewalCompany !== insurer).length;
    const afterRenewalCount = relevant.filter((r) => r.CurrentCompany === insurer).length;
    const insurerTotal = insurerExisting.length + insurerNewBiz.length;

    const preShare = total > 0 ? insurerExisting.length / total : 0;
    const afterShare = total > 0 ? afterRenewalCount / total : 0;
    const marketPreShare = 1; // 100% in context
    const marketAfterShare = preShare;

    const quoteChannels = buildChannelBreakdown(
      insurer ? relevant : data,
      'quote',
      insurer,
      channels?.channel_usage
    );
    const purchaseIntoRows = data.filter((r) => r.CurrentCompany === insurer && (r.Switchers === 'Switcher' || r.Switchers === 'New-to-market'));
    const purchaseFromRows = data.filter((r) => r.Switchers === 'Switcher' && r.PreRenewalCompany === insurer);
    const purchaseChannelsInto = buildChannelBreakdown(purchaseIntoRows, 'purchaseInto', insurer, channels?.channel_usage);
    const purchaseChannelsFrom = buildChannelBreakdown(purchaseFromRows, 'purchaseFrom', insurer, channels?.channel_usage);

    const nonShopPct = insurerExisting.length > 0 ? insurerNonShop.length / insurerExisting.length : 0;
    const shopPct = insurerExisting.length > 0 ? insurerShoppers.length / insurerExisting.length : 0;
    const retainedPct = insurerTotal > 0 ? retained / insurerTotal : 0;
    const switchedFromPct = insurerTotal > 0 ? switchedFrom / insurerTotal : 0;
    const switchedIntoPct = insurerTotal > 0 ? switchedInto / insurerTotal : 0;

    const marketNonShopPct = existing.length > 0 ? pct(nonShoppers.length, existing.length) : 0;
    const marketShopPct = existing.length > 0 ? pct(shoppers.length, existing.length) : 0;
    const marketRetainedPct = total > 0 ? (nonShoppers.length + shopStay.length) / total : 0;
    const marketSwitchedFromPct = total > 0 ? shopSwitch.length / total : 0;

    const marketAfterCount = total;
    const marketNonShop = nonShoppers.length;
    const marketRetainedCount = nonShoppers.length + shopStay.length;
    const marketSwitchedInto = newToMarket.length + data.filter((r) => r.Switchers === 'Switcher' && r.CurrentCompany !== r.PreRenewalCompany).length;
    const composition = afterRenewalCount > 0 && marketAfterCount > 0
      ? {
          nonShoppers: { label: 'Non Shoppers', pct: insurerNonShop.length / afterRenewalCount, marketPct: marketNonShop / marketAfterCount },
          retained: { label: 'Retained', pct: retained / afterRenewalCount, marketPct: marketRetainedCount / marketAfterCount },
          switchedInto: { label: 'Switched Into', pct: switchedInto / afterRenewalCount, marketPct: marketSwitchedInto / marketAfterCount },
        }
      : null;

    const flows = [
      { from: 'before-renewal', to: 'shoppers', count: insurerShoppers.length },
      { from: 'before-renewal', to: 'non-shoppers', count: insurerNonShop.length },
      { from: 'shoppers', to: 'retained', count: insurerShopStay.length },
      { from: 'shoppers', to: 'switched-from', count: insurerShopSwitch.length },
      { from: 'non-shoppers', to: 'after-renewal', count: insurerNonShop.length },
      { from: 'retained', to: 'after-renewal', count: insurerShopStay.length },
      { from: 'switched-from', to: 'after-renewal', count: insurerShopSwitch.length },
      { from: 'switched-into', to: 'after-renewal', count: switchedInto },
    ];

    return {
      insurer,
      beforeRenewal: {
        label: `${insurer} Before Renewal`,
        count: insurerExisting.length,
        pct: preShare,
        marketPct: marketPreShare,
        delta: preShare - marketPreShare,
      },
      shoppers: {
        label: 'Shoppers',
        count: insurerShoppers.length,
        pct: shopPct,
        marketPct: marketShopPct,
        delta: shopPct - marketShopPct,
      },
      nonShoppers: {
        label: 'Non Shoppers',
        count: insurerNonShop.length,
        pct: nonShopPct,
        marketPct: marketNonShopPct,
        delta: nonShopPct - marketNonShopPct,
      },
      retained: {
        label: 'Retained',
        count: retained,
        pct: retainedPct,
        marketPct: marketRetainedPct,
        delta: retainedPct - marketRetainedPct,
      },
      switchedFrom: {
        label: 'Switched From',
        count: switchedFrom,
        pct: switchedFromPct,
        marketPct: marketSwitchedFromPct,
        delta: switchedFromPct - marketSwitchedFromPct,
      },
      switchedInto: {
        label: 'Switched Into',
        count: switchedInto,
      },
      afterRenewal: {
        label: `${insurer} After Renewal`,
        count: afterRenewalCount,
        pct: afterShare,
        marketPct: marketAfterShare,
        delta: afterShare - marketAfterShare,
        composition,
      },
      quoteChannels,
      purchaseChannelsInto,
      purchaseChannelsFrom,
      flows,
      total,
      insurerTotal,
    };
  }

  // Market view
  const retainedCount = nonShoppers.length + shopStay.length;
  const switchedIntoCount = newToMarket.length + shopSwitch.length;
  const flows = [
    { from: 'before-renewal', to: 'shoppers', count: shoppers.length },
    { from: 'before-renewal', to: 'non-shoppers', count: nonShoppers.length },
    { from: 'shoppers', to: 'retained', count: shopStay.length },
    { from: 'shoppers', to: 'switched-from', count: shopSwitch.length },
    { from: 'non-shoppers', to: 'after-renewal', count: nonShoppers.length },
    { from: 'retained', to: 'after-renewal', count: shopStay.length },
    { from: 'switched-from', to: 'after-renewal', count: shopSwitch.length },
    { from: 'switched-into', to: 'after-renewal', count: switchedIntoCount },
  ];

  const quoteChannels = buildChannelBreakdown(data, 'quote', null, channels?.channel_usage);
  const purchaseChannelsInto = buildChannelBreakdown(shopSwitch, 'purchaseInto', null, channels?.channel_usage);
  const purchaseChannelsFrom = buildChannelBreakdown(shopSwitch, 'purchaseFrom', null, channels?.channel_usage);

  const composition = total > 0
    ? {
        nonShoppers: { label: 'Non Shoppers', pct: nonShoppers.length / total, marketPct: nonShoppers.length / total },
        retained: { label: 'Retained', pct: retainedCount / total, marketPct: retainedCount / total },
        switchedInto: { label: 'Switched Into', pct: switchedIntoCount / total, marketPct: switchedIntoCount / total },
      }
    : null;

  return {
    insurer: null,
    beforeRenewal: { label: 'Market Before Renewal', count: total, pct: 1, marketPct: 1, delta: 0 },
    shoppers: { label: 'Shoppers', count: shoppers.length, pct: pct(shoppers.length, existing.length), marketPct: pct(shoppers.length, existing.length), delta: 0 },
    nonShoppers: { label: 'Non Shoppers', count: nonShoppers.length, pct: pct(nonShoppers.length, existing.length), marketPct: pct(nonShoppers.length, existing.length), delta: 0 },
    retained: { label: 'Retained', count: retainedCount, pct: pct(retainedCount, total), marketPct: pct(retainedCount, total), delta: 0 },
    switchedFrom: { label: 'Switched From', count: shopSwitch.length, pct: pct(shopSwitch.length, total), marketPct: pct(shopSwitch.length, total), delta: 0 },
    switchedInto: { label: 'Switched Into', count: switchedIntoCount },
    afterRenewal: {
      label: 'Market After Renewal',
      count: total,
      pct: 1,
      marketPct: 1,
      delta: 0,
      composition,
    },
    quoteChannels,
    purchaseChannelsInto,
    purchaseChannelsFrom,
    flows,
    total,
    insurerTotal: null,
  };
}

/**
 * Build decision funnel tree data for Renewal Journey.
 * Returns nodes with id, label, pct (0-1), count, children, breakdown (for Won from / Lost to).
 * @param {Array} data - filtered rows
 * @param {string|null} insurer - selected insurer (null = market view)
 * @param {number} topN - top N brands for Won from / Lost to
 */
export function buildFunnelData(data, insurer, topN = 3) {
  if (!data?.length) return null;

  const total = data.length;

  // Market: all data. Insurer: rows where insurer is involved (pre or post)
  const relevant = insurer
    ? data.filter((r) => r.PreRenewalCompany === insurer || r.CurrentCompany === insurer)
    : data;

  if (relevant.length === 0 && insurer) return null;

  const newToMarket = data.filter((r) => r.Switchers === 'New-to-market');
  const existing = data.filter((r) => r.Switchers !== 'New-to-market');
  const nonShoppers = existing.filter((r) => r.Shoppers === 'Non-shoppers');
  const shoppers = existing.filter((r) => r.Shoppers === 'Shoppers');
  const shopStay = shoppers.filter((r) => r.Switchers === 'Non-switcher');
  const shopSwitch = shoppers.filter((r) => r.Switchers === 'Switcher');

  const pct = (n, base) => (base > 0 ? n / base : 0);

  // Insurer-specific segments
  const insurerExisting = insurer ? existing.filter((r) => r.PreRenewalCompany === insurer) : [];
  const insurerNewBiz = insurer ? newToMarket.filter((r) => r.CurrentCompany === insurer) : [];
  const insurerNonShop = insurer ? insurerExisting.filter((r) => r.Shoppers === 'Non-shoppers') : [];
  const insurerShoppers = insurer ? insurerExisting.filter((r) => r.Shoppers === 'Shoppers') : [];
  const insurerShopStay = insurer ? insurerShoppers.filter((r) => r.Switchers === 'Non-switcher') : [];
  const insurerShopSwitch = insurer ? insurerShoppers.filter((r) => r.Switchers === 'Switcher') : [];

  const topBrandsByCount = (arr, brandField) => {
    const counts = {};
    arr.forEach((r) => {
      const b = r[brandField];
      if (b) counts[b] = (counts[b] || 0) + 1;
    });
    const base = arr.length || 1;
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, topN)
      .map(([brand, c]) => ({ brand, pct: c / base }));
  };

  if (insurer) {
    const insurerTotal = insurerExisting.length + insurerNewBiz.length;
    const preShare = total > 0 ? insurerExisting.length / total : 0;
    const afterShare = total > 0 ? relevant.filter((r) => r.CurrentCompany === insurer).length / total : 0;
    const retained = insurerNonShop.length + insurerShopStay.length;
    const retainedPct = insurerTotal > 0 ? retained / insurerTotal : 0;
    const newBizPct = insurerTotal > 0 ? insurerNewBiz.length / insurerTotal : 0;

    // Market equivalents for comparison (insurer mode)
    const marketNewBizPct = pct(newToMarket.length, total);
    const marketNonShopPct = existing.length > 0 ? pct(nonShoppers.length, existing.length) : 0;
    const marketShopPct = existing.length > 0 ? pct(shoppers.length, existing.length) : 0;
    const marketShopStayPct = shoppers.length > 0 ? pct(shopStay.length, shoppers.length) : 0;
    const marketShopSwitchPct = shoppers.length > 0 ? pct(shopSwitch.length, shoppers.length) : 0;
    const marketRetainedPct = total > 0 ? (nonShoppers.length + shopStay.length) / total : 0;
    const allBrands = new Set([
      ...data.map((r) => r.PreRenewalCompany),
      ...data.map((r) => r.CurrentCompany),
    ].filter(Boolean));
    const insurerCount = allBrands.size;
    const marketPreShare = insurerCount > 0 ? 1 / insurerCount : 0;
    // After renewal: compare to pre-renewal share (gaining/losing share)
    const marketAfterShare = preShare;

    const lostTo = topBrandsByCount(
      data.filter((r) => r.Switchers === 'Switcher' && r.PreRenewalCompany === insurer),
      'CurrentCompany'
    );
    const switchersToUs = data.filter((r) => r.Switchers === 'Switcher' && r.CurrentCompany === insurer);
    const newBizToUs = newToMarket.filter((r) => r.CurrentCompany === insurer);
    const totalWon = switchersToUs.length + newBizToUs.length;
    const fromCounts = {};
    switchersToUs.forEach((r) => {
      const b = r.PreRenewalCompany;
      if (b) fromCounts[b] = (fromCounts[b] || 0) + 1;
    });
    if (newBizToUs.length > 0) fromCounts['New to market'] = newBizToUs.length;
    const wonFrom = Object.entries(fromCounts)
      .map(([brand, c]) => ({ brand, pct: totalWon > 0 ? c / totalWon : 0 }))
      .sort((a, b) => b.pct - a.pct)
      .slice(0, topN);

    // Flows for arrow rendering: { from, to, count }
    const flows = [
      { from: 'new-to-market', to: 'new-biz', count: insurerNewBiz.length },
      { from: 'pre-renewal', to: 'non-shoppers', count: insurerNonShop.length },
      { from: 'pre-renewal', to: 'shoppers', count: insurerShoppers.length },
      { from: 'shoppers', to: 'shop-stay', count: insurerShopStay.length },
      { from: 'shoppers', to: 'shop-switch', count: insurerShopSwitch.length },
      { from: 'non-shoppers', to: 'retained', count: insurerNonShop.length },
      { from: 'shop-stay', to: 'retained', count: insurerShopStay.length },
      { from: 'new-biz', to: 'won-from', count: insurerNewBiz.length },
      { from: 'shop-switch', to: 'lost-to', count: insurerShopSwitch.length },
      { from: 'switchers-in', to: 'won-from', count: switchersToUs.length },
    ];

    const nonShopPctInsurer = insurerExisting.length > 0 ? insurerNonShop.length / insurerExisting.length : 0;
    const shopPctInsurer = insurerExisting.length > 0 ? insurerShoppers.length / insurerExisting.length : 0;
    const shopStayPctInsurer = insurerShoppers.length > 0 ? insurerShopStay.length / insurerShoppers.length : 0;
    const shopSwitchPctInsurer = insurerShoppers.length > 0 ? insurerShopSwitch.length / insurerShoppers.length : 0;

    return {
      preRenewalShare: {
        label: 'Pre-renewal market share',
        pct: preShare,
        count: insurerExisting.length,
        marketPct: marketPreShare,
        delta: preShare - marketPreShare,
      },
      newBusiness: {
        label: 'New business acquisition',
        pct: insurerTotal > 0 ? insurerNewBiz.length / insurerTotal : 0,
        count: insurerNewBiz.length,
        marketPct: marketNewBizPct,
        delta: newBizPct - marketNewBizPct,
      },
      nonShoppers: {
        label: 'Non-shoppers',
        pct: nonShopPctInsurer,
        count: insurerNonShop.length,
        marketPct: marketNonShopPct,
        delta: nonShopPctInsurer - marketNonShopPct,
      },
      shoppers: {
        label: 'Shoppers',
        pct: shopPctInsurer,
        count: insurerShoppers.length,
        marketPct: marketShopPct,
        delta: shopPctInsurer - marketShopPct,
        shopStay: {
          label: 'Shopped then stayed',
          pct: shopStayPctInsurer,
          count: insurerShopStay.length,
          marketPct: marketShopStayPct,
          delta: shopStayPctInsurer - marketShopStayPct,
        },
        shopSwitch: {
          label: 'Shopped then switched',
          pct: shopSwitchPctInsurer,
          count: insurerShopSwitch.length,
          marketPct: marketShopSwitchPct,
          delta: shopSwitchPctInsurer - marketShopSwitchPct,
        },
      },
      retained: {
        label: 'Retained',
        pct: retainedPct,
        count: retained,
        marketPct: marketRetainedPct,
        delta: retainedPct - marketRetainedPct,
      },
      wonFrom: { label: 'Won from (top 3)', breakdown: wonFrom, count: wonFrom.length },
      lostTo: { label: 'Lost to (top 3)', breakdown: lostTo, count: lostTo.length },
      afterRenewalShare: {
        label: 'After renewal market share',
        pct: afterShare,
        count: relevant.filter((r) => r.CurrentCompany === insurer).length,
        marketPct: marketAfterShare,
        delta: afterShare - marketAfterShare,
      },
      customerBase: {
        retained: retainedPct,
        newBusiness: newBizPct,
      },
      flows,
      total,
      insurerTotal,
    };
  }

  // Market view
  const newBizPct = pct(newToMarket.length, total);
  const existingPct = pct(existing.length, total);
  const nonShopPct = existing.length > 0 ? pct(nonShoppers.length, existing.length) : 0;
  const shopPct = existing.length > 0 ? pct(shoppers.length, existing.length) : 0;
  const shopStayPct = shoppers.length > 0 ? pct(shopStay.length, shoppers.length) : 0;
  const shopSwitchPct = shoppers.length > 0 ? pct(shopSwitch.length, shoppers.length) : 0;
  const retainedCount = nonShoppers.length + shopStay.length;
  const retainedPct = total > 0 ? retainedCount / total : 0;

  const switchedTo = topBrandsByCount(shopSwitch, 'CurrentCompany');

  // Flows for market view
  const flows = [
    { from: 'new-to-market', to: 'new-biz', count: newToMarket.length },
    { from: 'pre-renewal', to: 'non-shoppers', count: nonShoppers.length },
    { from: 'pre-renewal', to: 'shoppers', count: shoppers.length },
    { from: 'shoppers', to: 'shop-stay', count: shopStay.length },
    { from: 'shoppers', to: 'shop-switch', count: shopSwitch.length },
    { from: 'non-shoppers', to: 'retained', count: nonShoppers.length },
    { from: 'shop-stay', to: 'retained', count: shopStay.length },
    { from: 'new-biz', to: 'won-from', count: newToMarket.length },
    { from: 'shop-switch', to: 'won-from', count: shopSwitch.length },
  ];

  return {
    preRenewalShare: { label: 'Pre-renewal market share', pct: 1, count: total },
    newBusiness: { label: 'New business acquisition', pct: newBizPct, count: newToMarket.length },
    nonShoppers: { label: 'Non-shoppers', pct: nonShopPct, count: nonShoppers.length },
    shoppers: {
      label: 'Shoppers',
      pct: shopPct,
      count: shoppers.length,
      shopStay: { label: 'Shopped then stayed', pct: shopStayPct, count: shopStay.length },
      shopSwitch: { label: 'Shopped then switched', pct: shopSwitchPct, count: shopSwitch.length },
    },
    retained: { label: 'Retained', pct: retainedPct, count: retainedCount },
    wonFrom: { label: 'Switched to (top 3)', breakdown: switchedTo, count: switchedTo.length },
    lostTo: null,
    afterRenewalShare: { label: 'After renewal market share', pct: 1, count: total },
    customerBase: {
      retained: retainedPct,
      newBusiness: newBizPct,
    },
    flows,
    total,
    insurerTotal: null,
  };
}
