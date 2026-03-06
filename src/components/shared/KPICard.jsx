import { COLORS } from '../../utils/brandConstants';
import { formatPct, formatNumber, formatCurrency, formatGap } from '../../utils/formatters';
import styles from './KPICard.module.css';

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
      <div className={styles.card}>
        <div className={styles.label}>{label}</div>
        <div className={styles.valueSuppressed}>—</div>
        {suppressionMessage && (
          <div className={styles.suppressionMsg}>{suppressionMessage}</div>
        )}
      </div>
    );
  }

  const gapColour = isInsurerMode ? getGapColour(gap, favourableDirection) : null;

  return (
    <div className={styles.card}>
      <div className={styles.label}>{label}</div>

      {/* Primary value */}
      <div style={{
        fontSize: 'var(--font-card-value)',
        fontWeight: 'bold',
        color: isInsurerMode ? COLORS.magenta : COLORS.grey,
        margin: '8px 0 4px',
        lineHeight: 1.1,
      }}>
        {formatValue(value, format)}
      </div>

      {/* Indicative badge */}
      {indicative && (
        <div className={styles.indicativeBadge}>Indicative</div>
      )}

      {/* Trend */}
      {trend && (
        <div className={styles.trendRow}>
          <span className={styles.trendArrow}>{TREND_ARROW[trend] || '—'}</span>
          {trendValue !== null && trendValue !== undefined && formatValue(trendValue, format)}
        </div>
      )}

      {/* Insurer mode: market value and gap */}
      {isInsurerMode && (
        <div className={styles.marketSection}>
          <div className={styles.marketLabel}>
            Market: {formatValue(marketValue, format)}
          </div>
          {gap !== null && gap !== undefined && (
            <div className={styles.gapValue} style={{ color: gapColour }}>
              {formatGap(gap, format)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** @deprecated Use CSS module class styles.card instead */
export const cardStyle = styles.card;
/** @deprecated Use CSS module class styles.label instead */
export const labelStyle = styles.label;
