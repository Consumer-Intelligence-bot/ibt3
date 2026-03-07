import { COLORS, FONT } from '../../utils/brandConstants';

const fmtPct = (v) => `${(v * 100).toFixed(1)}%`;

function MiniPairedBar({ label, insValue, mktValue }) {
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
        <span style={{ fontSize: 10, color: COLORS.magenta, fontWeight: 'bold' }}> {fmtPct(insValue)}</span>
      </div>
      <div>
        <div style={{
          height: 10, width: `${mktW.toFixed(0)}%`, minWidth: 2,
          backgroundColor: COLORS.grey, borderRadius: 2, opacity: 0.5, display: 'inline-block',
        }} />
        <span style={{ fontSize: 10, color: COLORS.grey }}> {fmtPct(mktValue)}</span>
      </div>
    </div>
  );
}

export default function PremiumChangeVsMarket({ insurer, market }) {
  if (!insurer || !market) return null;

  return (
    <div style={{
      backgroundColor: '#FFF', borderRadius: 8,
      boxShadow: '0 1px 4px rgba(0,0,0,0.10)',
      padding: '12px 16px', fontFamily: FONT.family, marginTop: 8,
    }}>
      <div style={{
        fontSize: 10, color: '#666', textTransform: 'uppercase',
        letterSpacing: '0.5px', marginBottom: 8,
      }}>
        Renewal premium change
      </div>
      <MiniPairedBar label="Higher" insValue={insurer.higher} mktValue={market.higher} />
      <MiniPairedBar label="Unchanged" insValue={insurer.unchanged} mktValue={market.unchanged} />
      <MiniPairedBar label="Lower" insValue={insurer.lower} mktValue={market.lower} />
    </div>
  );
}
