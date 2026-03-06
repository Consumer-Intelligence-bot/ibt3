import { COLORS, FONT } from '../../utils/brandConstants';

/**
 * Butterfly chart — wins on the left, losses on the right.
 * Top 3 competitors per side with direct labels.
 *
 * Props:
 *   wonFrom    Array<{ brand: string, value: number }>  Brands won from (% share)
 *   lostTo     Array<{ brand: string, value: number }>  Brands lost to (% share)
 *   callout    string   Footer callout text
 */
export default function ButterflyChart({ wonFrom = [], lostTo = [], callout }) {
  const allValues = [...wonFrom, ...lostTo].map(d => d.value);
  const maxValue = Math.max(...allValues, 1);

  return (
    <div style={{
      backgroundColor: COLORS.white,
      borderRadius: 8,
      boxShadow: '0 1px 4px rgba(0,0,0,0.10)',
      padding: 20,
      fontFamily: FONT.family,
    }}>
      {/* Column headers */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 120px 1fr',
        marginBottom: 16,
      }}>
        <div style={{
          fontSize: 13,
          fontWeight: 'bold',
          color: COLORS.green,
          textAlign: 'right',
          paddingRight: 12,
        }}>
          Won from
        </div>
        <div />
        <div style={{
          fontSize: 13,
          fontWeight: 'bold',
          color: COLORS.red,
          textAlign: 'left',
          paddingLeft: 12,
        }}>
          Lost to
        </div>
      </div>

      {/* Rows */}
      {Array.from({ length: Math.max(wonFrom.length, lostTo.length) }).map((_, i) => {
        const won = wonFrom[i];
        const lost = lostTo[i];
        return (
          <div key={i} style={{
            display: 'grid',
            gridTemplateColumns: '1fr 120px 1fr',
            alignItems: 'center',
            marginBottom: 10,
          }}>
            {/* Won from bar (grows right-to-left) */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8 }}>
              {won && (
                <>
                  <span style={{ fontSize: 11, color: COLORS.darkGrey, whiteSpace: 'nowrap' }}>
                    {won.value.toFixed(1)}%
                  </span>
                  <div style={{
                    height: 20,
                    width: `${(won.value / maxValue) * 100}%`,
                    minWidth: 4,
                    backgroundColor: COLORS.green,
                    borderRadius: 3,
                    transition: 'width 0.3s ease',
                  }} />
                </>
              )}
            </div>

            {/* Brand label (centre) */}
            <div style={{
              textAlign: 'center',
              fontSize: 12,
              fontWeight: 'bold',
              color: COLORS.darkGrey,
              padding: '0 4px',
            }}>
              {won?.brand || lost?.brand || ''}
              {won && lost && won.brand !== lost.brand && (
                <span style={{ fontWeight: 'normal', color: COLORS.grey }}>
                  {' / '}{lost.brand}
                </span>
              )}
            </div>

            {/* Lost to bar (grows left-to-right) */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {lost && (
                <>
                  <div style={{
                    height: 20,
                    width: `${(lost.value / maxValue) * 100}%`,
                    minWidth: 4,
                    backgroundColor: COLORS.red,
                    borderRadius: 3,
                    transition: 'width 0.3s ease',
                  }} />
                  <span style={{ fontSize: 11, color: COLORS.darkGrey, whiteSpace: 'nowrap' }}>
                    {lost.value.toFixed(1)}%
                  </span>
                </>
              )}
            </div>
          </div>
        );
      })}

      {/* Callout */}
      {callout && (
        <div style={{
          marginTop: 16,
          paddingTop: 12,
          borderTop: `1px solid ${COLORS.lightGrey}`,
          fontSize: 12,
          color: COLORS.darkGrey,
          fontStyle: 'italic',
        }}>
          {callout}
        </div>
      )}
    </div>
  );
}
