import { useMemo, useState, useEffect } from 'react';
import {
  ComposedChart, Area, Line,
  XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from 'recharts';
import { useDashboard } from '../../context/DashboardContext';
import KPICard from '../shared/KPICard';
import Placeholder from '../shared/Placeholder';
import ReasonChart from '../screen4/ReasonChart';
import { getReasons } from '../../api';
import { proxyReasonsForShopping, proxyReasonsForNotShopping, getSegmentCounts } from '../../utils/measures/whyTheyMoveMeasures';
import { COLORS, FONT } from '../../utils/brandConstants';
import { checkSuppression, checkTrendSuppression } from '../../utils/governance';
import {
  shoppingRate,
  nonShoppingRate,
  shoppingRateByMonth,
  pcwUsageRate,
  trendChange,
  generateNarrative,
} from '../../utils/measures/screen2Measures';
import NarrativeCard from './NarrativeCard';
import styles from './ShopOrStay.module.css';

// ── Trend KPI card (custom: CI Blue for arrow + value) ──────────────────────────

function TrendKPICard({ marketTrend, marketSupp, insurerMode, insurerTrend, insurerSupp, indicative }) {
  const showMarket = !!(marketTrend && marketSupp?.show);
  const showInsurer = !!(insurerMode && insurerTrend && insurerSupp?.show);
  const primaryTrend = insurerMode
    ? (showInsurer ? insurerTrend : null)
    : (showMarket ? marketTrend : null);

  function trendLabel(trend) {
    if (!trend) return '—';
    const arrow = trend.changePts > 0 ? '▲' : trend.changePts < 0 ? '▼' : '—';
    const prefix = trend.changePts > 0 ? '+' : '';
    const pts = (trend.changePts * 100).toFixed(1);
    return `${arrow} ${prefix}${pts}pts`;
  }

  return (
    <div className={styles.trendCard}>
      <div className={styles.trendLabel}>Trend</div>

      {primaryTrend ? (
        <>
          <div style={{
            fontSize: FONT.cardValue,
            fontWeight: 'bold',
            color: COLORS.blue,
            margin: '8px 0 4px',
            lineHeight: 1.1,
          }}>
            {trendLabel(primaryTrend)}
          </div>

          {indicative && (
            <div className={styles.indicativeBadge}>Indicative</div>
          )}

          <div className={styles.trendVs}>vs prior period</div>

          {insurerMode && showMarket && (
            <div className={styles.marketSection}>
              <div className={styles.marketLabel}>
                Market: {trendLabel(marketTrend)}
              </div>
            </div>
          )}
        </>
      ) : (
        <>
          <div className={styles.trendSuppressed}>—</div>
          <div className={styles.trendSuppressedMsg}>
            {(marketSupp && !marketSupp.show)
              ? marketSupp.message
              : 'Insufficient data for trend analysis'}
          </div>
        </>
      )}
    </div>
  );
}

// ── Custom tooltip for line chart ───────────────────────────────────────────────

// Keys used for the CI band — excluded from tooltip display
const CI_KEYS = new Set(['ciBase', 'bandWidth']);

function LineTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const visible = payload.filter(p => !CI_KEYS.has(p.dataKey));
  if (!visible.length) return null;
  const n = payload[0]?.payload?.n;
  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipTitle}>{label}</div>
      {visible.map(p => (
        <div key={p.dataKey} style={{ color: p.stroke, marginBottom: '2px' }}>
          {p.name}: {typeof p.value === 'number' ? `${p.value.toFixed(1)}%` : '—'}
        </div>
      ))}
      {n !== undefined && (
        <div className={styles.tooltipN}>n = {n}</div>
      )}
    </div>
  );
}

// ── Square dot renderer for insurer line ────────────────────────────────────────

function SquareDot(props) {
  const { cx, cy } = props;
  const size = 8;
  if (cx == null || cy == null) return null;
  return (
    <rect
      x={cx - size / 2}
      y={cy - size / 2}
      width={size}
      height={size}
      fill={COLORS.magenta}
    />
  );
}

function SquareDotActive(props) {
  const { cx, cy } = props;
  const size = 10;
  if (cx == null || cy == null) return null;
  return (
    <rect
      x={cx - size / 2}
      y={cy - size / 2}
      width={size}
      height={size}
      fill={COLORS.magenta}
    />
  );
}

// ── Main component ──────────────────────────────────────────────────────────────

export default function ShopOrStay() {
  const { filteredData, mode, selectedInsurer, product } = useDashboard();
  const insurerMode = mode === 'insurer' && !!selectedInsurer;

  const [reasonsQ8, setReasonsQ8] = useState(null);
  const [reasonsQ19, setReasonsQ19] = useState(null);
  const [reasonsApiError, setReasonsApiError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setReasonsApiError(false);
    const load = async () => {
      try {
        const [r8, r19] = await Promise.all([
          getReasons({ product: product || 'motor', brand: insurerMode ? selectedInsurer : null, questionGroup: 'reasons-for-shopping' }),
          getReasons({ product: product || 'motor', brand: insurerMode ? selectedInsurer : null, questionGroup: 'reasons-for-not-shopping' }),
        ]);
        if (!cancelled && r8?.reasons?.length) setReasonsQ8({ reasons: r8.reasons, base_n: r8.base_n });
        if (!cancelled && r19?.reasons?.length) setReasonsQ19({ reasons: r19.reasons, base_n: r19.base_n });
      } catch {
        if (!cancelled) setReasonsApiError(true);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [insurerMode, selectedInsurer, product]);

  // ── Market measures ────────────────────────────────────────────────────────────
  const marketShopRate    = shoppingRate(filteredData);
  const marketNonShopRate = nonShoppingRate(filteredData);
  const marketPCW         = pcwUsageRate(filteredData);
  const marketTrend       = trendChange(filteredData);

  // ── Insurer measures ───────────────────────────────────────────────────────────
  const insurerShopRate    = insurerMode ? shoppingRate(filteredData, selectedInsurer)    : null;
  const insurerNonShopRate = insurerMode ? nonShoppingRate(filteredData, selectedInsurer) : null;
  const insurerPCW         = insurerMode ? pcwUsageRate(filteredData, selectedInsurer)    : null;
  const insurerTrend       = insurerMode ? trendChange(filteredData, selectedInsurer)     : null;

  // ── Suppression ────────────────────────────────────────────────────────────────
  const insurerN = insurerMode
    ? filteredData.filter(r => r.CurrentCompany === selectedInsurer).length
    : 0;
  const insurerSuppression = insurerMode ? checkSuppression(insurerN) : null;
  const isIndicative = insurerSuppression?.level === 'indicative';

  const marketTrendSupp = marketTrend
    ? checkTrendSuppression(marketTrend.recentN, marketTrend.previousN)
    : null;
  const insurerTrendSupp = insurerTrend
    ? checkTrendSuppression(insurerTrend.recentN, insurerTrend.previousN)
    : null;

  // ── Narrative ──────────────────────────────────────────────────────────────────
  const narrativeText = insurerMode
    ? generateNarrative(selectedInsurer, insurerShopRate, marketShopRate)
    : null;

  // ── Chart data ─────────────────────────────────────────────────────────────────
  const marketMonthly = useMemo(
    () => shoppingRateByMonth(filteredData),
    [filteredData]
  );
  const insurerMonthly = useMemo(
    () => (insurerMode ? shoppingRateByMonth(filteredData, selectedInsurer) : []),
    [filteredData, selectedInsurer, insurerMode]
  );

  const chartData = useMemo(() => {
    return marketMonthly.map(m => {
      // 95% confidence interval: ±1.96 × sqrt(p(1-p)/n)
      const margin = m.n > 1 ? 1.96 * Math.sqrt(m.rate * (1 - m.rate) / m.n) : 0;
      const ciLow  = Math.max(0, m.rate - margin) * 100;
      const ciHigh = Math.min(100, m.rate + margin) * 100;
      const ins = insurerMonthly.find(i => i.month === m.month);
      return {
        monthDisplay: m.monthDisplay,
        marketRate:   parseFloat((m.rate * 100).toFixed(1)),
        // Band rendered as stacked areas: ciBase (transparent) + bandWidth (grey fill)
        ciBase:     parseFloat(ciLow.toFixed(1)),
        bandWidth:  parseFloat((ciHigh - ciLow).toFixed(1)),
        n:          m.n,
        insurerRate: ins != null ? parseFloat((ins.rate * 100).toFixed(1)) : null,
      };
    });
  }, [marketMonthly, insurerMonthly]);

  // ── KPI card props helper ──────────────────────────────────────────────────────
  function kpiProps(label, marketVal, insurerVal, format, favourableDirection) {
    const value = insurerMode ? insurerVal : marketVal;
    return {
      label,
      value,
      format,
      marketValue:         insurerMode ? marketVal  : undefined,
      gap:                 insurerMode && marketVal !== null && insurerVal !== null
                             ? insurerVal - marketVal : undefined,
      favourableDirection: insurerMode ? favourableDirection : undefined,
      indicative:          isIndicative,
    };
  }

  return (
    <div className={styles.container}>

      {/* ── Row 1: KPI cards ──────────────────────────────────────────────────── */}
      <div className={styles.kpiRow}>

        <KPICard {...kpiProps('Shopping Rate', marketShopRate, insurerShopRate, 'pct', 'neutral')} />
        <KPICard {...kpiProps('Non-Shopping Rate', marketNonShopRate, insurerNonShopRate, 'pct', 'neutral')} />

        <TrendKPICard
          marketTrend={marketTrend}
          marketSupp={marketTrendSupp}
          insurerMode={insurerMode}
          insurerTrend={insurerTrend}
          insurerSupp={insurerTrendSupp}
          indicative={isIndicative}
        />

        <KPICard {...kpiProps('PCW Usage (of shoppers)', marketPCW, insurerPCW, 'pct', 'neutral')} />

      </div>

      {/* ── Row 2: Charts (60/40) ─────────────────────────────────────────────── */}
      <div className={styles.chartGrid}>

        {/* Left: shopping rate line chart with confidence band */}
        <div className={styles.chartCard}>
          <div className={styles.chartTitle}>Shopping rate over time</div>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={chartData} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="monthDisplay"
                tick={{ fontSize: 11, fontFamily: FONT.family }}
              />
              <YAxis
                tickFormatter={v => `${v}%`}
                domain={['auto', 'auto']}
                tick={{ fontSize: 11, fontFamily: FONT.family }}
              />
              <Tooltip content={<LineTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: '11px', fontFamily: FONT.family, paddingTop: '8px' }}
              />

              {/* Confidence band: transparent base + grey fill on top (stacked areas) */}
              <Area
                type="monotone"
                dataKey="ciBase"
                stackId="ci"
                fill="transparent"
                stroke="none"
                legendType="none"
                activeDot={false}
                isAnimationActive={false}
                tooltipType="none"
              />
              <Area
                type="monotone"
                dataKey="bandWidth"
                stackId="ci"
                fill={COLORS.confidenceFill}
                stroke="none"
                legendType="none"
                activeDot={false}
                isAnimationActive={false}
                name="95% CI"
                tooltipType="none"
              />

              {/* Market line: CI Grey, circle dots */}
              <Line
                type="monotone"
                dataKey="marketRate"
                name="Market"
                stroke={COLORS.grey}
                strokeWidth={2}
                dot={{ r: 4, fill: COLORS.grey, strokeWidth: 0 }}
                activeDot={{ r: 6, fill: COLORS.grey }}
              />

              {/* Insurer overlay: CI Magenta, square dots */}
              {insurerMode && (
                <Line
                  type="monotone"
                  dataKey="insurerRate"
                  name={selectedInsurer}
                  stroke={COLORS.magenta}
                  strokeWidth={2}
                  dot={<SquareDot />}
                  activeDot={<SquareDotActive />}
                  connectNulls={false}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Right: Why they shop / don't shop */}
        <div className={styles.reasonColumn}>
          {reasonsQ8?.reasons?.length ? (
            <ReasonChart title="Why Customers Shop (Q8)" reasons={reasonsQ8.reasons} baseN={reasonsQ8.base_n} insurerMode={!!insurerMode} />
          ) : reasonsApiError && proxyReasonsForShopping(filteredData)?.length ? (
            <ReasonChart title="Why Customers Shop (Q8) (proxy)" reasons={proxyReasonsForShopping(filteredData)} baseN={getSegmentCounts(filteredData, insurerMode ? selectedInsurer : null).shopping} insurerMode={!!insurerMode} />
          ) : (
            <Placeholder title="Why Customers Shop (Q8)" dataNeeded="Additional survey response data to display detailed reasons" />
          )}
          {reasonsQ19?.reasons?.length ? (
            <ReasonChart title="Why Customers Don't Shop (Q19)" reasons={reasonsQ19.reasons} baseN={reasonsQ19.base_n} insurerMode={!!insurerMode} />
          ) : reasonsApiError && proxyReasonsForNotShopping(filteredData)?.length ? (
            <ReasonChart title="Why Customers Don't Shop (Q19) (proxy)" reasons={proxyReasonsForNotShopping(filteredData)} baseN={getSegmentCounts(filteredData, insurerMode ? selectedInsurer : null)['not-shopping']} insurerMode={!!insurerMode} />
          ) : (
            <Placeholder title="Why Customers Don't Shop (Q19)" dataNeeded="Additional survey response data to display detailed reasons" />
          )}
        </div>

      </div>

      {/* ── Narrative card (insurer mode only, not suppressed) ─────────────────── */}
      {insurerMode && narrativeText && insurerSuppression?.show !== false && (
        <NarrativeCard insurer={selectedInsurer} text={narrativeText} />
      )}

    </div>
  );
}
