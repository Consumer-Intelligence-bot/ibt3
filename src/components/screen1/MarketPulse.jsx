import { useMemo } from 'react';
import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
} from 'recharts';
import { useDashboard } from '../../context/DashboardContext';
import { COLORS } from '../../utils/brandConstants';
import { formatPct } from '../../utils/formatters';
import { checkSuppression } from '../../utils/governance';
import {
  shoppingRate,
  switchingRate,
  shopAndStayRate,
  pcwUsageRate,
  ratesByMonth,
  trendChange,
  priceDirectionSplit,
} from '../../utils/measures/marketPulseMeasures';
import styles from './MarketPulse.module.css';

const TREND_ARROW = { up: '▲', down: '▼', flat: '—' };

function Sparkline({ values, color }) {
  if (!values?.length) return null;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const w = 120;
  const h = 24;
  const pts = values
    .map((v, i) => {
      const x = (i / (values.length - 1 || 1)) * w;
      const y = h - ((v - min) / range) * (h - 4) - 2;
      return `${x},${y}`;
    })
    .join(' ');
  return (
    <svg width={w} height={h} style={{ display: 'block', marginTop: 4 }}>
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeOpacity={0.8}
      />
    </svg>
  );
}

function MarketPulseKPICard({ label, value, sparklineValues, trend, trendValue, n, suppressed }) {
  const arrow = trend ? TREND_ARROW[trend.changePts > 0 ? 'up' : trend.changePts < 0 ? 'down' : 'flat'] : null;
  const trendColor = trend?.changePts > 0 ? COLORS.green : trend?.changePts < 0 ? COLORS.red : COLORS.grey;

  if (suppressed) {
    return (
      <div className={styles.kpiCard}>
        <div className={styles.kpiLabel}>{label}</div>
        <div className={styles.kpiSuppressed}>—</div>
        <div className={styles.kpiSuppressedText}>Insufficient data</div>
      </div>
    );
  }

  return (
    <div className={styles.kpiCard}>
      <div className={styles.kpiLabel}>{label}</div>
      <div className={styles.kpiValue}>
        {formatPct(value)}
        {arrow && trend?.changePts != null && (
          <span className={styles.kpiTrendInline} style={{ color: trendColor }}>
            {arrow} {(trend.changePts * 100).toFixed(1)}pts
          </span>
        )}
      </div>
      <Sparkline values={sparklineValues} color={COLORS.magenta} />
      <div className={styles.kpiSampleSize}>n={n?.toLocaleString()}</div>
    </div>
  );
}


function TrendTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const p = payload[0]?.payload;
  return (
    <div className={styles.tooltip}>
      <div className={styles.tooltipTitle}>{label}</div>
      {payload.map((entry) => (
        <div key={entry.dataKey} style={{ color: entry.color, marginBottom: 2 }}>
          {entry.name}: {formatPct(entry.value)}
        </div>
      ))}
      {p?.n != null && <div className={styles.tooltipN}>n={p.n}</div>}
    </div>
  );
}

export default function MarketPulse() {
  const { filteredData, filteredDataMotor, filteredDataHome, selectedInsurer, mode } = useDashboard();
  const data = filteredData;
  const insurer = mode === 'insurer' ? selectedInsurer : null;

  const ratesByMonthData = useMemo(() => ratesByMonth(data, insurer), [data, insurer]);
  const last12 = useMemo(() => ratesByMonthData.slice(-12), [ratesByMonthData]);

  const shopping = useMemo(() => shoppingRate(data, insurer), [data, insurer]);
  const switching = useMemo(() => switchingRate(data, insurer), [data, insurer]);
  const shopStay = useMemo(() => shopAndStayRate(data, insurer), [data, insurer]);
  const pcw = useMemo(() => pcwUsageRate(data, insurer), [data, insurer]);

  const n = data.length;
  const mainSupp = useMemo(() => checkSuppression(n), [n]);
  const pcwSupp = useMemo(() => {
    const shoppers = data.filter((r) => r.Shoppers === 'Shoppers').length;
    return checkSuppression(shoppers);
  }, [data]);

  const shoppingTrend = useMemo(() => trendChange(data, insurer, 'shoppingRate'), [data, insurer]);
  const switchingTrend = useMemo(() => trendChange(data, insurer, 'switchingRate'), [data, insurer]);
  const shopStayTrend = useMemo(() => trendChange(data, insurer, 'shopAndStayRate'), [data, insurer]);
  const pcwTrend = useMemo(() => trendChange(data, insurer, 'pcwUsageRate'), [data, insurer]);

  const priceSplit = useMemo(() => priceDirectionSplit(data, insurer), [data, insurer]);

  const motorRates = useMemo(
    () => ({
      shopping: shoppingRate(filteredDataMotor, null),
      switching: switchingRate(filteredDataMotor, null),
      shopStay: shopAndStayRate(filteredDataMotor, null),
      pcw: pcwUsageRate(filteredDataMotor, null),
      n: filteredDataMotor.length,
    }),
    [filteredDataMotor]
  );
  const homeRates = useMemo(
    () => ({
      shopping: shoppingRate(filteredDataHome, null),
      switching: switchingRate(filteredDataHome, null),
      shopStay: shopAndStayRate(filteredDataHome, null),
      pcw: pcwUsageRate(filteredDataHome, null),
      n: filteredDataHome.length,
    }),
    [filteredDataHome]
  );

  const showHomeVsMotor = !insurer && filteredDataMotor.length > 0 && filteredDataHome.length > 0;

  return (
    <div className={styles.container}>
      {/* KPI cards */}
      <div className={styles.kpiRow}>
        <MarketPulseKPICard
          label="Shopping Rate"
          value={shopping}
          sparklineValues={last12.map((m) => m.shoppingRate)}
          trend={shoppingTrend}
          n={n}
          suppressed={!mainSupp.show}
        />
        <MarketPulseKPICard
          label="Switching Rate"
          value={switching}
          sparklineValues={last12.map((m) => m.switchingRate)}
          trend={switchingTrend}
          n={n}
          suppressed={!mainSupp.show}
        />
        <MarketPulseKPICard
          label="Shop & Stay Rate"
          value={shopStay}
          sparklineValues={last12.map((m) => m.shopAndStayRate)}
          trend={shopStayTrend}
          n={n}
          suppressed={!mainSupp.show}
        />
        <MarketPulseKPICard
          label="PCW Usage"
          value={pcw}
          sparklineValues={last12.map((m) => m.pcwUsageRate)}
          trend={pcwTrend}
          n={data.filter((r) => r.Shoppers === 'Shoppers').length}
          suppressed={!pcwSupp.show}
        />
      </div>

      {/* Trend chart */}
      <div className={styles.chartPanel}>
        <div className={styles.chartTitle}>Trend (last 12 periods)</div>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={ratesByMonthData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
            <XAxis dataKey="monthDisplay" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={(v) => formatPct(v)} domain={[0, 1]} tick={{ fontSize: 11 }} />
            <Tooltip content={<TrendTooltip />} />
            <Legend />
            <Line
              type="monotone"
              dataKey="shoppingRate"
              name="Shopping Rate"
              stroke={COLORS.magenta}
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="switchingRate"
              name="Switching Rate"
              stroke={COLORS.blue}
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="shopAndStayRate"
              name="Shop & Stay Rate"
              stroke={COLORS.green}
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Comparison panels */}
      <div style={{ display: 'grid', gridTemplateColumns: showHomeVsMotor ? '1fr 1fr' : '1fr', gap: 24 }}>
        {showHomeVsMotor && (
          <div className={styles.panel}>
            <div className={styles.panelTitle}>Home vs Motor</div>
            <div className={styles.comparisonGrid}>
              <div>
                <div className={styles.comparisonSectionLabel}>Motor (n={motorRates.n})</div>
                <div className={styles.comparisonItem}>Shopping: {formatPct(motorRates.shopping)}</div>
                <div className={styles.comparisonItem}>Switching: {formatPct(motorRates.switching)}</div>
                <div className={styles.comparisonItem}>Shop & Stay: {formatPct(motorRates.shopStay)}</div>
                <div className={styles.comparisonItem}>PCW: {formatPct(motorRates.pcw)}</div>
              </div>
              <div>
                <div className={styles.comparisonSectionLabel}>Home (n={homeRates.n})</div>
                <div className={styles.comparisonItem}>Shopping: {formatPct(homeRates.shopping)}</div>
                <div className={styles.comparisonItem}>Switching: {formatPct(homeRates.switching)}</div>
                <div className={styles.comparisonItem}>Shop & Stay: {formatPct(homeRates.shopStay)}</div>
                <div className={styles.comparisonItem}>PCW: {formatPct(homeRates.pcw)}</div>
              </div>
            </div>
          </div>
        )}

        <div className={styles.panel}>
          <div className={styles.panelTitle}>Price Direction Split</div>
          <div className={styles.priceBar}>
            <div
              className={styles.priceBarSegment}
              style={{
                width: `${(priceSplit.higher || 0) * 100}%`,
                backgroundColor: COLORS.red,
                minWidth: priceSplit.higher > 0 ? 8 : 0,
              }}
              title={`Higher: ${formatPct(priceSplit.higher)}`}
            />
            <div
              className={styles.priceBarSegment}
              style={{
                width: `${(priceSplit.unchanged || 0) * 100}%`,
                backgroundColor: COLORS.grey,
                minWidth: priceSplit.unchanged > 0 ? 8 : 0,
              }}
              title={`Unchanged: ${formatPct(priceSplit.unchanged)}`}
            />
            <div
              className={styles.priceBarSegment}
              style={{
                width: `${(priceSplit.lower || 0) * 100}%`,
                backgroundColor: COLORS.green,
                minWidth: priceSplit.lower > 0 ? 8 : 0,
              }}
              title={`Lower: ${formatPct(priceSplit.lower)}`}
            />
          </div>
          <div className={styles.priceSummary}>
            Higher {formatPct(priceSplit.higher)} · Unchanged {formatPct(priceSplit.unchanged)} · Lower{' '}
            {formatPct(priceSplit.lower)} (n={priceSplit.n})
          </div>
        </div>
      </div>
    </div>
  );
}
