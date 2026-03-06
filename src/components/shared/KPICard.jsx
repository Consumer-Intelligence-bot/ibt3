import { COLORS, FONT } from '../../utils/brandConstants';
import { formatPct, formatNumber, formatCurrency, formatGap } from '../../utils/formatters';
import SuppressionMessage from './SuppressionMessage';

const TREND_ARROW = { up: '▲', down: '▼', flat: '—' };

function getGapColour(gap, favourableDirection) {
  if (!favourableDirection || favourableDirection === 'neutral') return COLORS.blue;
  if (gap === null || gap === undefined) return COLORS.grey;
  const isPositive = gap > 0;
  if (favourableDirection === 'higher') return isPositive ? COLORS.green : COLORS.red;
  if (favourableDirection === 'lower') return isPositive ? COLORS.red : COLORS.green;
  return COLORS.blue;
}

function formatValue(value, format) {
  if (format === 'pct') return formatPct(value);
  if (format === 'currency') return formatCurrency(value);
  return formatNumber(value);
}

/**
 * KPI Card — two modes:
 *   Market mode: shows a single value with label.
 *   Insurer mode: shows insurer value, market value, gap, colour coding.
 *
 * Props:
 *   label            string     Card title
 *   value            number     Primary value
 *   format           "pct" | "number" | "currency"
 *   marketValue      number     Market comparison (insurer mode)
 *   gap              number     Insurer minus market
 *   favourableDirection  "higher" | "lower" | "neutral"
 *   trend            "up" | "down" | "flat" | null
 *   trendValue       number     Numeric trend change
 *   indicative       boolean    Show "Indicative" badge
 *   suppressed       boolean    Show suppression state
 *   suppressionMessage string   Message shown when suppressed
 */
export default function KPICard({
  label,
  value,
  format = 'number',
  marketValue,
  gap,
  favourableDirection,
  trend,
  trendValue,
  indicative = false,
  suppressed = false,
  suppressionMessage,
}) {
  const isInsurerMode = marketValue !== undefined && marketValue !== null;

  if (suppressed) {
    return (
      <div style={cardStyle}>
        <div style={labelStyle}>{label}</div>
        <div style={{ color: '#ccc', fontSize: '28px', fontWeight: 'bold', margin: '8px 0' }}>—</div>
        {suppressionMessage && (
          <div style={{ fontSize: '11px', color: '#999', marginTop: '4px' }}>
            {suppressionMessage}
          </div>
        )}
      </div>
    );
  }

  const gapColour = isInsurerMode ? getGapColour(gap, favourableDirection) : null;

  return (
    <div style={cardStyle}>
      <div style={labelStyle}>{label}</div>

      {/* Primary value */}
      <div style={{
        fontSize: FONT.cardValue,
        fontWeight: 'bold',
        color: isInsurerMode ? COLORS.magenta : COLORS.grey,
        margin: '8px 0 4px',
        lineHeight: 1.1,
      }}>
        {formatValue(value, format)}
      </div>

      {/* Indicative badge */}
      {indicative && (
        <div style={{
          display: 'inline-block',
          fontSize: '10px',
          color: '#F5A623',
          border: '1px solid #F5A623',
          borderRadius: '3px',
          padding: '1px 5px',
          marginBottom: '6px',
        }}>
          Indicative
        </div>
      )}

      {/* Trend */}
      {trend && (
        <div style={{ fontSize: '12px', color: COLORS.grey, marginBottom: '4px' }}>
          <span style={{ marginRight: '4px' }}>{TREND_ARROW[trend] || '—'}</span>
          {trendValue !== null && trendValue !== undefined && formatValue(trendValue, format)}
        </div>
      )}

      {/* Insurer mode: market value and gap */}
      {isInsurerMode && (
        <div style={{ borderTop: '1px solid #eee', marginTop: '8px', paddingTop: '8px' }}>
          <div style={{ fontSize: '11px', color: COLORS.grey }}>
            Market: {formatValue(marketValue, format)}
          </div>
          {gap !== null && gap !== undefined && (
            <div style={{ fontSize: '12px', color: gapColour, fontWeight: 'bold', marginTop: '2px' }}>
              {formatGap(gap, format)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export const cardStyle = {
  backgroundColor: COLORS.white,
  borderRadius: '8px',
  boxShadow: '0 1px 4px rgba(0,0,0,0.10)',
  padding: '16px',
  minWidth: '160px',
  fontFamily: FONT.family,
};

export const labelStyle = {
  fontSize: FONT.cardLabel,
  color: '#444',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  lineHeight: 1.3,
};
