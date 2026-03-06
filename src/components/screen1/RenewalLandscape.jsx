import { useState, useMemo } from 'react';
import {
  ComposedChart, Area, Line,
  BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, LabelList,
} from 'recharts';
import { useDashboard } from '../../context/DashboardContext';
import KPICard from '../shared/KPICard';
import Placeholder from '../shared/Placeholder';
import { COLORS, FONT } from '../../utils/brandConstants';
import { checkSuppression } from '../../utils/governance';
import {
  totalRenewals,
  priceUpPct,
  priceDownPct,
  priceUnchangedPct,
  priceChangeByMonth,
  priceChangeBands,
  avgPriceChange,
} from '../../utils/measures/screen1Measures';

// ── Shared chart styles ────────────────────────────────────────────────────────

const chartCard = {
  backgroundColor: COLORS.white,
  borderRadius: '8px',
  boxShadow: '0 1px 4px rgba(0,0,0,0.10)',
  padding: '16px',
};

const chartTitle = {
  fontSize: '14px',
  fontWeight: 'bold',
  fontFamily: FONT.family,
  color: '#333',
  marginBottom: '12px',
};

// ── Custom tooltips ────────────────────────────────────────────────────────────

function AreaTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const n = payload[0]?.payload?.n;
  return (
    <div style={{
      backgroundColor: '#fff',
      border: '1px solid #ddd',
      borderRadius: '6px',
      padding: '10px',
      fontFamily: FONT.family,
      fontSize: '12px',
      minWidth: '160px',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: '6px' }}>{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ color: p.fill || p.stroke, marginBottom: '2px' }}>
          {p.name}: {typeof p.value === 'number' ? `${p.value.toFixed(1)}%` : '—'}
        </div>
      ))}
      {n !== undefined && (
        <div style={{ color: '#888', marginTop: '6px', borderTop: '1px solid #eee', paddingTop: '4px' }}>
          n = {n}
        </div>
      )}
    </div>
  );
}

function BandTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      backgroundColor: '#fff',
      border: '1px solid #ddd',
      borderRadius: '6px',
      padding: '10px',
      fontFamily: FONT.family,
      fontSize: '12px',
    }}>
      <div style={{ fontWeight: 'bold', marginBottom: '6px' }}>{label}</div>
      {payload.map(p =>
        p.value !== null && p.value !== undefined ? (
          <div key={p.dataKey} style={{ color: p.fill, marginBottom: '2px' }}>
            {p.name}: {p.value.toFixed(1)}%
          </div>
        ) : null
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function RenewalLandscape() {
  const { filteredData, mode, selectedInsurer } = useDashboard();
  const [bandDirection, setBandDirection] = useState('up');

  const insurerMode = mode === 'insurer' && !!selectedInsurer;

  // ── Market measures ──────────────────────────────────────────────────────────
  const marketTotal     = totalRenewals(filteredData);
  const marketUp        = priceUpPct(filteredData);
  const marketDown      = priceDownPct(filteredData);
  const marketUnchanged = priceUnchangedPct(filteredData);
  const marketAvgUp     = avgPriceChange(filteredData, 'up');

  const marketMonthly = useMemo(
    () => priceChangeByMonth(filteredData),
    [filteredData]
  );

  // ── Insurer measures (when in insurer mode) ──────────────────────────────────
  const insurerTotal     = insurerMode ? totalRenewals(filteredData, selectedInsurer) : null;
  const insurerUp        = insurerMode ? priceUpPct(filteredData, selectedInsurer) : null;
  const insurerDown      = insurerMode ? priceDownPct(filteredData, selectedInsurer) : null;
  const insurerUnchanged = insurerMode ? priceUnchangedPct(filteredData, selectedInsurer) : null;
  const insurerAvgUp     = insurerMode ? avgPriceChange(filteredData, 'up', selectedInsurer) : null;

  const insurerMonthly = useMemo(
    () => (insurerMode ? priceChangeByMonth(filteredData, selectedInsurer) : []),
    [filteredData, selectedInsurer, insurerMode]
  );

  const insurerSuppression = insurerMode ? checkSuppression(insurerTotal) : null;
  const isIndicative = insurerSuppression?.level === 'indicative';

  // ── Stacked area chart data ──────────────────────────────────────────────────
  const areaData = useMemo(() => {
    return marketMonthly.map(m => {
      const ins = insurerMonthly.find(i => i.month === m.month);
      return {
        monthDisplay:   m.monthDisplay,
        Higher:         parseFloat((m.upPct        * 100).toFixed(1)),
        Lower:          parseFloat((m.downPct      * 100).toFixed(1)),
        Unchanged:      parseFloat((m.unchangedPct * 100).toFixed(1)),
        n:              m.n,
        insurerHigher:  ins != null ? parseFloat((ins.upPct * 100).toFixed(1)) : null,
      };
    });
  }, [marketMonthly, insurerMonthly]);

  // ── Band chart data ──────────────────────────────────────────────────────────
  const bandData = useMemo(() => {
    const market = priceChangeBands(filteredData, bandDirection);
    const ins    = insurerMode ? priceChangeBands(filteredData, bandDirection, selectedInsurer) : [];
    return market.map(mb => ({
      band:       mb.band,
      marketPct:  parseFloat((mb.pct * 100).toFixed(1)),
      insurerPct: insurerMode
        ? parseFloat(((ins.find(ib => ib.band === mb.band)?.pct ?? 0) * 100).toFixed(1))
        : null,
    }));
  }, [filteredData, bandDirection, insurerMode, selectedInsurer]);

  const bandColor = bandDirection === 'up' ? COLORS.red : COLORS.green;

  // ── Helpers for KPI card props ───────────────────────────────────────────────
  function kpiProps(label, marketVal, insurerVal, format, favourableDirection) {
    const value = insurerMode ? insurerVal : marketVal;
    return {
      label,
      value,
      format,
      marketValue:         insurerMode ? marketVal    : undefined,
      gap:                 insurerMode && marketVal !== null && insurerVal !== null
                             ? insurerVal - marketVal : undefined,
      favourableDirection: insurerMode ? favourableDirection : undefined,
      indicative:          isIndicative,
    };
  }

  const showAvgUp = (insurerMode ? insurerAvgUp : marketAvgUp) !== null;

  return (
    <div style={{ fontFamily: FONT.family }}>

      {/* ── Row 1: KPI cards ───────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '24px' }}>

        <KPICard {...kpiProps('Total Renewals', marketTotal, insurerTotal, 'number', 'neutral')} />
        <KPICard {...kpiProps('Price Up',       marketUp,    insurerUp,    'pct',    'lower')}   />
        <KPICard {...kpiProps('Price Down',     marketDown,  insurerDown,  'pct',    'higher')}  />
        <KPICard {...kpiProps('Price Unchanged',marketUnchanged, insurerUnchanged, 'pct', 'neutral')} />

        {showAvgUp && (
          <KPICard {...kpiProps(
            'Avg. Increase',
            marketAvgUp,
            insurerAvgUp,
            'currency',
            'lower'
          )} />
        )}
      </div>

      {/* ── Row 2: Charts (60/40) ──────────────────────────────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '3fr 2fr',
        gap: '16px',
        marginBottom: '24px',
      }}>

        {/* Left: stacked area chart — price pressure over time */}
        <div style={chartCard}>
          <div style={chartTitle}>Price pressure over time</div>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={areaData} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="monthDisplay"
                tick={{ fontSize: 11, fontFamily: FONT.family }}
              />
              <YAxis
                tickFormatter={v => `${v}%`}
                domain={[0, 100]}
                tick={{ fontSize: 11, fontFamily: FONT.family }}
              />
              <Tooltip content={<AreaTooltip />} />
              <Legend wrapperStyle={{ fontSize: '11px', fontFamily: FONT.family, paddingTop: '8px' }} />

              <Area
                type="monotone"
                dataKey="Higher"
                stackId="1"
                fill="rgba(244,54,76,0.70)"
                stroke={COLORS.red}
                strokeWidth={1}
              />
              <Area
                type="monotone"
                dataKey="Lower"
                stackId="1"
                fill="rgba(72,162,63,0.70)"
                stroke={COLORS.green}
                strokeWidth={1}
              />
              <Area
                type="monotone"
                dataKey="Unchanged"
                stackId="1"
                fill="rgba(84,88,90,0.50)"
                stroke={COLORS.grey}
                strokeWidth={1}
              />

              {insurerMode && (
                <Line
                  type="monotone"
                  dataKey="insurerHigher"
                  name={`${selectedInsurer} Higher`}
                  stroke={COLORS.magenta}
                  strokeWidth={2}
                  strokeDasharray="5 3"
                  dot={{ r: 3, fill: COLORS.magenta }}
                  connectNulls={false}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Right: horizontal bar chart — price change bands */}
        <div style={chartCard}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <div style={chartTitle}>Price change bands</div>
            <div style={{ display: 'flex', gap: '6px' }}>
              {[
                { key: 'up',   label: 'Higher', color: COLORS.red   },
                { key: 'down', label: 'Lower',  color: COLORS.green },
              ].map(({ key, label, color }) => {
                const active = bandDirection === key;
                return (
                  <button
                    key={key}
                    onClick={() => setBandDirection(key)}
                    style={{
                      padding: '3px 12px',
                      fontSize: '12px',
                      fontFamily: FONT.family,
                      borderRadius: '4px',
                      cursor: 'pointer',
                      border: `1px solid ${active ? color : '#ccc'}`,
                      backgroundColor: active ? color : '#fff',
                      color: active ? '#fff' : '#555',
                      fontWeight: active ? 'bold' : 'normal',
                    }}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={bandData}
              layout="vertical"
              margin={{ top: 0, right: 52, bottom: 0, left: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
              <XAxis
                type="number"
                tickFormatter={v => `${v}%`}
                tick={{ fontSize: 10, fontFamily: FONT.family }}
              />
              <YAxis
                type="category"
                dataKey="band"
                width={115}
                tick={{ fontSize: 10, fontFamily: FONT.family }}
              />
              <Tooltip content={<BandTooltip />} />
              {insurerMode && (
                <Legend wrapperStyle={{ fontSize: '11px', fontFamily: FONT.family }} />
              )}

              <Bar
                dataKey="marketPct"
                name={insurerMode ? 'Market' : 'Share'}
                fill={insurerMode ? COLORS.grey : bandColor}
                maxBarSize={18}
              >
                {!insurerMode && (
                  <LabelList
                    dataKey="marketPct"
                    position="right"
                    formatter={v => `${v?.toFixed(1)}%`}
                    style={{ fontSize: '10px', fontFamily: FONT.family, fill: '#555' }}
                  />
                )}
              </Bar>

              {insurerMode && (
                <Bar
                  dataKey="insurerPct"
                  name={selectedInsurer}
                  fill={COLORS.magenta}
                  maxBarSize={18}
                />
              )}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Row 3: Placeholder ─────────────────────────────────────────────── */}
      <div style={{ marginBottom: '24px' }}>
        <Placeholder
          title="Premium distribution (Q43a)"
          dataNeeded="Additional survey response data to display premium distribution"
        />
      </div>

    </div>
  );
}
