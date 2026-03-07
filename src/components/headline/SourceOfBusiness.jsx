import { FONT } from '../../utils/brandConstants';
import MiniPairedBar from './MiniPairedBar';

export default function SourceOfBusiness({ insurer, market }) {
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
        Source of business
      </div>
      <MiniPairedBar label="PCW" insValue={insurer.pcw} mktValue={market.pcw} />
      <MiniPairedBar label="Direct / Other" insValue={insurer.direct} mktValue={market.direct} />
    </div>
  );
}
