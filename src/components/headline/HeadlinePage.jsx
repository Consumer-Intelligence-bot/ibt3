import { useMemo } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import { COLORS, FONT } from '../../utils/brandConstants';
import { cardStyle } from '../shared/KPICard';
import { buildFunnelData } from '../../utils/measures/renewalJourneyMeasures';
import { shoppingRate } from '../../utils/measures/marketPulseMeasures';
import { checkSuppression } from '../../utils/governance';
import ComparisonBar from './ComparisonBar';
import ButterflyChart from './ButterflyChart';

/**
 * Default story values from the brief.
 * Used when no insurer is selected or data does not override.
 */
const DEFAULTS = {
  preShare: 10.5,
  postShare: 10.6,
  netMovement: 0.1,
  shoppingAdmiral: 77.4,
  shoppingMarket: 77.5,
  retentionAdmiral: 42.2,
  retentionMarket: 38.4,
  shopStayAdmiral: 25.9,
  shopStayMarket: 20.7,
  newBizAdmiral: 1.0,
  newBizMarket: 0.5,
  wonFrom: [
    { brand: 'Aviva', value: 13.1 },
    { brand: 'Hastings', value: 10.6 },
    { brand: 'Churchill', value: 7.8 },
  ],
  lostTo: [
    { brand: 'Aviva', value: 20.7 },
    { brand: 'AA', value: 8.7 },
    { brand: 'TBC', value: 0 },
  ],
  base: 2561,
};

function deriveTag(admiral, market) {
  const gap = admiral - market;
  if (Math.abs(gap) < 0.5) return 'In line';
  return gap > 0 ? 'Ahead' : 'Below';
}

export default function HeadlinePage() {
  const { filteredData, selectedInsurer, mode } = useDashboard();
  const insurer = mode === 'insurer' ? selectedInsurer : null;

  const n = filteredData.length;
  const suppression = useMemo(() => checkSuppression(n), [n]);

  // Compute live metrics when an insurer is selected
  const funnel = useMemo(
    () => (insurer ? buildFunnelData(filteredData, insurer, 3) : null),
    [filteredData, insurer],
  );
  const marketShopping = useMemo(
    () => shoppingRate(filteredData, null),
    [filteredData],
  );
  const insurerShopping = useMemo(
    () => (insurer ? shoppingRate(filteredData, insurer) : null),
    [filteredData, insurer],
  );

  // Resolve values: live data if insurer selected & available, else brief defaults
  const live = funnel && insurer;
  const preShare = live ? +(funnel.preRenewalShare.pct * 100).toFixed(1) : DEFAULTS.preShare;
  const postShare = live ? +(funnel.afterRenewalShare.pct * 100).toFixed(1) : DEFAULTS.postShare;
  const netMovement = +(postShare - preShare).toFixed(1);

  const shoppingAdmiral = live && insurerShopping != null
    ? +(insurerShopping * 100).toFixed(1) : DEFAULTS.shoppingAdmiral;
  const shoppingMarket = marketShopping != null
    ? +(marketShopping * 100).toFixed(1) : DEFAULTS.shoppingMarket;

  const retentionAdmiral = live ? +(funnel.retained.pct * 100).toFixed(1) : DEFAULTS.retentionAdmiral;
  const retentionMarket = live ? +(funnel.retained.marketPct * 100).toFixed(1) : DEFAULTS.retentionMarket;

  const shopStayAdmiral = live ? +(funnel.shoppers.shopStay.pct * 100).toFixed(1) : DEFAULTS.shopStayAdmiral;
  const shopStayMarket = live ? +(funnel.shoppers.shopStay.marketPct * 100).toFixed(1) : DEFAULTS.shopStayMarket;

  const newBizAdmiral = live ? +(funnel.newBusiness.pct * 100).toFixed(1) : DEFAULTS.newBizAdmiral;
  const newBizMarket = live ? +(funnel.newBusiness.marketPct * 100).toFixed(1) : DEFAULTS.newBizMarket;

  const wonFrom = live && funnel.wonFrom?.breakdown?.length
    ? funnel.wonFrom.breakdown.map(b => ({ brand: b.brand, value: +(b.pct * 100).toFixed(1) }))
    : DEFAULTS.wonFrom;
  const lostTo = live && funnel.lostTo?.breakdown?.length
    ? funnel.lostTo.breakdown.map(b => ({ brand: b.brand, value: +(b.pct * 100).toFixed(1) }))
    : DEFAULTS.lostTo;

  const base = live ? n : DEFAULTS.base;
  const brandName = insurer || 'Admiral';

  const movementColor = netMovement > 0 ? COLORS.green : netMovement < 0 ? COLORS.red : COLORS.grey;
  const movementPrefix = netMovement > 0 ? '+' : '';

  if (!suppression.show && insurer) {
    return (
      <div style={{ padding: 60, textAlign: 'center', color: '#999', fontFamily: FONT.family }}>
        <p>Insufficient data to display headline for {insurer}.</p>
      </div>
    );
  }

  return (
    <div style={{ fontFamily: FONT.family, maxWidth: 900, margin: '0 auto' }}>

      {/* ── HEADLINE ─────────────────────────────────────────── */}
      <div style={{ marginBottom: 8 }}>
        <h1 style={{
          fontSize: 22,
          fontWeight: 'bold',
          color: COLORS.darkGrey,
          margin: '0 0 6px',
          lineHeight: 1.3,
        }}>
          Customers shop at the market rate, but {brandName} keeps more of them
        </h1>
        <p style={{
          fontSize: 14,
          color: COLORS.grey,
          margin: 0,
          lineHeight: 1.5,
        }}>
          Retention and acquisition both beat market, lifting share from {preShare}% to {postShare}% through renewal.
        </p>
      </div>

      {/* ── TOP: OUTCOME ─────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        gap: 16,
        marginBottom: 32,
        marginTop: 20,
        justifyContent: 'center',
        flexWrap: 'wrap',
      }}>
        {/* Pre-renewal share */}
        <div style={{ ...cardStyle, textAlign: 'center', flex: '1 1 200px', maxWidth: 240 }}>
          <div style={sectionLabel}>Pre-renewal share</div>
          <div style={{ fontSize: 36, fontWeight: 'bold', color: COLORS.darkGrey, margin: '8px 0' }}>
            {preShare}%
          </div>
        </div>

        {/* Net movement */}
        <div style={{
          ...cardStyle,
          textAlign: 'center',
          flex: '1 1 180px',
          maxWidth: 200,
          borderTop: `4px solid ${movementColor}`,
        }}>
          <div style={sectionLabel}>Net movement</div>
          <div style={{ fontSize: 36, fontWeight: 'bold', color: movementColor, margin: '8px 0' }}>
            {movementPrefix}{netMovement.toFixed(1)} pts
          </div>
        </div>

        {/* Post-renewal share */}
        <div style={{ ...cardStyle, textAlign: 'center', flex: '1 1 200px', maxWidth: 240 }}>
          <div style={sectionLabel}>Post-renewal share</div>
          <div style={{ fontSize: 36, fontWeight: 'bold', color: COLORS.magenta, margin: '8px 0' }}>
            {postShare}%
          </div>
        </div>
      </div>

      {/* ── MIDDLE: WHY THIS HAPPENED ────────────────────────── */}
      <div style={{
        backgroundColor: COLORS.white,
        borderRadius: 8,
        boxShadow: '0 1px 4px rgba(0,0,0,0.10)',
        padding: 20,
        marginBottom: 32,
      }}>
        <div style={{
          fontSize: 15,
          fontWeight: 'bold',
          color: COLORS.darkGrey,
          marginBottom: 4,
        }}>
          Why this happened
        </div>
        <p style={{
          fontSize: 13,
          color: COLORS.grey,
          margin: '0 0 20px',
          lineHeight: 1.5,
        }}>
          Customers are just as likely to shop around. {brandName} performs better when they do.
        </p>

        <ComparisonBar
          label="Shopping rate"
          admiralValue={shoppingAdmiral}
          marketValue={shoppingMarket}
          tag={deriveTag(shoppingAdmiral, shoppingMarket)}
        />
        <ComparisonBar
          label="Retention"
          admiralValue={retentionAdmiral}
          marketValue={retentionMarket}
          tag={deriveTag(retentionAdmiral, retentionMarket)}
        />
        <ComparisonBar
          label="Shopped and stayed"
          admiralValue={shopStayAdmiral}
          marketValue={shopStayMarket}
          tag={deriveTag(shopStayAdmiral, shopStayMarket)}
        />
        <ComparisonBar
          label="New business acquisition"
          admiralValue={newBizAdmiral}
          marketValue={newBizMarket}
          tag={deriveTag(newBizAdmiral, newBizMarket)}
          maxValue={Math.max(newBizAdmiral, newBizMarket) * 2.5}
        />
      </div>

      {/* ── BOTTOM: COMPETITIVE EXCHANGE ─────────────────────── */}
      <div style={{ marginBottom: 32 }}>
        <div style={{
          fontSize: 15,
          fontWeight: 'bold',
          color: COLORS.darkGrey,
          marginBottom: 12,
        }}>
          Competitive exchange
        </div>
        <ButterflyChart
          wonFrom={wonFrom}
          lostTo={lostTo}
          callout="Aviva is the main two-way battleground."
        />
      </div>

      {/* ── FOOTER ───────────────────────────────────────────── */}
      <div style={{
        fontSize: 11,
        color: COLORS.grey,
        textAlign: 'center',
        paddingBottom: 24,
      }}>
        Base: {base.toLocaleString()} respondents
      </div>
    </div>
  );
}

const sectionLabel = {
  fontSize: 11,
  color: '#666',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
};
