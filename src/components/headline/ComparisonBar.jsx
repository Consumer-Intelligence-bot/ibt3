import { COLORS, FONT } from '../../utils/brandConstants';
import { formatPct } from '../../utils/formatters';

const TAG_COLOURS = {
  Ahead: COLORS.green,
  Below: COLORS.red,
  'In line': COLORS.grey,
};

export default function ComparisonBar({ label, insValue, mktValue, tag, insurerName, maxVal = 1.0, onClickMore }) {
  const insPctWidth = maxVal > 0 ? (insValue / maxVal) * 100 : 0;
  const mktPctWidth = maxVal > 0 ? (mktValue / maxVal) * 100 : 0;
  const tagCol = TAG_COLOURS[tag] || COLORS.grey;

  return (
    <div style={{ fontFamily: FONT.family }}>
      {/* Label row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 'bold', color: '#4D5153' }}>{label}</span>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <span style={{ fontSize: 11, fontWeight: 'bold', color: tagCol, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            {tag}
          </span>
          {onClickMore && (
            <button
              onClick={onClickMore}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: COLORS.magenta, fontSize: 11, fontWeight: 'bold',
                fontFamily: FONT.family, whiteSpace: 'nowrap', padding: 0,
              }}
            >
              Click for more ▼
            </button>
          )}
        </div>
      </div>

      {/* Bar track */}
      <div style={{ position: 'relative', height: 24, backgroundColor: COLORS.lightGrey, borderRadius: 4 }}>
        <div style={{
          position: 'absolute', left: 0, top: 2, bottom: 2,
          width: `${insPctWidth.toFixed(1)}%`,
          backgroundColor: COLORS.magenta, borderRadius: 3,
          transition: 'width 0.3s ease',
        }} />
        <div style={{
          position: 'absolute', left: `${mktPctWidth.toFixed(1)}%`,
          top: 0, bottom: 0, width: 3,
          backgroundColor: COLORS.grey, borderRadius: 1,
        }} />
      </div>

      {/* Value labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        <span style={{ fontSize: 11, fontWeight: 'bold', color: COLORS.magenta }}>
          {insurerName} {formatPct(insValue)}
        </span>
        <span style={{ fontSize: 11, color: COLORS.grey }}>
          Market {formatPct(mktValue)}
        </span>
      </div>
    </div>
  );
}
