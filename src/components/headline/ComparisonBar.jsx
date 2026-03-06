import { COLORS, FONT } from '../../utils/brandConstants';

/**
 * Dumbbell-style comparison bar: Admiral value vs Market benchmark.
 * Shows a filled bar for Admiral, a thin marker for Market, direct labels, and an insight tag.
 *
 * Props:
 *   label          string   Row label (e.g. "Shopping rate")
 *   admiralValue   number   Admiral percentage (e.g. 77.4)
 *   marketValue    number   Market percentage (e.g. 77.5)
 *   tag            string   Insight tag ("In line", "Ahead", "Below")
 *   maxValue       number   Scale maximum (default 100)
 */
export default function ComparisonBar({
  label,
  admiralValue,
  marketValue,
  tag,
  maxValue = 100,
}) {
  const admiralPct = (admiralValue / maxValue) * 100;
  const marketPct = (marketValue / maxValue) * 100;

  const tagColour =
    tag === 'Ahead' ? COLORS.green : tag === 'Below' ? COLORS.red : COLORS.grey;

  return (
    <div style={{ marginBottom: 16, fontFamily: FONT.family }}>
      {/* Label row */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        marginBottom: 6,
      }}>
        <span style={{ fontSize: 13, color: COLORS.darkGrey, fontWeight: 'bold' }}>
          {label}
        </span>
        <span style={{
          fontSize: 11,
          fontWeight: 'bold',
          color: tagColour,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
        }}>
          {tag}
        </span>
      </div>

      {/* Bar track */}
      <div style={{
        position: 'relative',
        height: 24,
        backgroundColor: COLORS.lightGrey,
        borderRadius: 4,
        overflow: 'visible',
      }}>
        {/* Admiral bar */}
        <div style={{
          position: 'absolute',
          left: 0,
          top: 2,
          bottom: 2,
          width: `${admiralPct}%`,
          backgroundColor: COLORS.magenta,
          borderRadius: 3,
          transition: 'width 0.3s ease',
        }} />

        {/* Market marker line */}
        <div style={{
          position: 'absolute',
          left: `${marketPct}%`,
          top: 0,
          bottom: 0,
          width: 3,
          backgroundColor: COLORS.grey,
          borderRadius: 1,
        }} />
      </div>

      {/* Value labels */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginTop: 4,
        fontSize: 11,
      }}>
        <span style={{ color: COLORS.magenta, fontWeight: 'bold' }}>
          Admiral {admiralValue.toFixed(1)}%
        </span>
        <span style={{ color: COLORS.grey }}>
          Market {marketValue.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}
