import { FONT } from '../../utils/brandConstants';
import MiniPairedBar from './MiniPairedBar';

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
