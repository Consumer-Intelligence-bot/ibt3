import { COLORS, FONT } from '../../utils/brandConstants';
import { formatPct } from '../../utils/formatters';

export default function ButterflyChart({ wonFrom, lostTo, callout }) {
  const allVals = [...wonFrom.map(w => w.pct), ...lostTo.map(l => l.pct)];
  const maxVal = allVals.length > 0 ? Math.max(...allVals) : 0.01;
  const nRows = Math.max(wonFrom.length, lostTo.length);

  return (
    <div style={{
      backgroundColor: '#FFF', borderRadius: 8,
      boxShadow: '0 1px 4px rgba(0,0,0,0.10)',
      padding: 20, fontFamily: FONT.family,
    }}>
      {/* Headers */}
      <div style={{ display: 'flex', marginBottom: 16 }}>
        <div style={{ flex: 5, textAlign: 'right', paddingRight: 12, fontSize: 13, fontWeight: 'bold', color: COLORS.green }}>
          Won from
        </div>
        <div style={{ flex: 2 }} />
        <div style={{ flex: 5, textAlign: 'left', paddingLeft: 12, fontSize: 13, fontWeight: 'bold', color: COLORS.red }}>
          Lost to
        </div>
      </div>

      {/* Rows */}
      {Array.from({ length: nRows }, (_, i) => {
        const won = wonFrom[i];
        const lost = lostTo[i];
        const brand = won?.brand || lost?.brand || '';

        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
            {/* Won bar (right-aligned) */}
            <div style={{ flex: 5, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8 }}>
              {won && (
                <>
                  <span style={{ fontSize: 11, color: '#4D5153', whiteSpace: 'nowrap' }}>{formatPct(won.pct)}</span>
                  <div style={{
                    height: 20, width: `${(won.pct / maxVal) * 100}%`, minWidth: 4,
                    backgroundColor: COLORS.green, borderRadius: 3,
                  }} />
                </>
              )}
            </div>

            {/* Brand label */}
            <div style={{
              flex: 2, textAlign: 'center', fontSize: 12, fontWeight: 'bold',
              color: '#4D5153', padding: '0 4px', whiteSpace: 'nowrap',
            }}>
              {brand}
            </div>

            {/* Lost bar (left-aligned) */}
            <div style={{ flex: 5, display: 'flex', alignItems: 'center', gap: 8 }}>
              {lost && (
                <>
                  <div style={{
                    height: 20, width: `${(lost.pct / maxVal) * 100}%`, minWidth: 4,
                    backgroundColor: COLORS.red, borderRadius: 3,
                  }} />
                  <span style={{ fontSize: 11, color: '#4D5153', whiteSpace: 'nowrap' }}>{formatPct(lost.pct)}</span>
                </>
              )}
            </div>
          </div>
        );
      })}

      {/* Callout */}
      {callout && (
        <div style={{
          marginTop: 16, paddingTop: 12,
          borderTop: `1px solid ${COLORS.lightGrey}`,
          fontSize: 12, color: '#4D5153', fontStyle: 'italic',
        }}>
          {callout}
        </div>
      )}
    </div>
  );
}
