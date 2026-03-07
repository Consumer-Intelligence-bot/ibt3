import { COLORS } from '../../utils/brandConstants';
import { formatPct } from '../../utils/formatters';

export default function MiniPairedBar({ label, insValue, mktValue }) {
  const maxVal = Math.max(insValue, mktValue, 0.01);
  const insW = (insValue / maxVal) * 100;
  const mktW = (mktValue / maxVal) * 100;

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: 10, color: '#4D5153', marginBottom: 3, fontWeight: 'bold' }}>{label}</div>
      <div style={{ marginBottom: 2 }}>
        <div style={{
          height: 10, width: `${insW.toFixed(0)}%`, minWidth: 2,
          backgroundColor: COLORS.magenta, borderRadius: 2, display: 'inline-block',
        }} />
        <span style={{ fontSize: 10, color: COLORS.magenta, fontWeight: 'bold' }}> {formatPct(insValue)}</span>
      </div>
      <div>
        <div style={{
          height: 10, width: `${mktW.toFixed(0)}%`, minWidth: 2,
          backgroundColor: COLORS.grey, borderRadius: 2, opacity: 0.5, display: 'inline-block',
        }} />
        <span style={{ fontSize: 10, color: COLORS.grey }}> {formatPct(mktValue)}</span>
      </div>
    </div>
  );
}
