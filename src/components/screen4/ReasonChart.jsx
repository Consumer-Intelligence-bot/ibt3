import { COLORS } from '../../utils/brandConstants';
import styles from './ReasonChart.module.css';

/**
 * Horizontal ranked bar chart for reason breakdowns.
 * Spec: CI Blue bars, brand in CI Violet when insurer selected. Longest bar at top.
 */
export default function ReasonChart({ title, reasons, baseN, insurerMode }) {
  if (!reasons?.length) return null;

  const maxPct = Math.max(...reasons.map((r) => r.market_pct ?? r.insurer_pct ?? 0), 0.01);

  return (
    <div className={styles.card}>
      <div className={styles.title}>{title}</div>
      {baseN && (
        <div className={styles.baseN}>
          <span style={{ color: COLORS.grey }}>
            Market n={typeof baseN.market === 'number' ? baseN.market.toLocaleString() : (typeof baseN === 'number' ? baseN.toLocaleString() : baseN.market ?? '—')}
          </span>
          {insurerMode && (baseN.insurer != null || baseN.insurer === 0) && (
            <span style={{ color: COLORS.green, fontWeight: 'bold' }}>
              Company n={(baseN.insurer ?? 0).toLocaleString()}
            </span>
          )}
        </div>
      )}
      <div className={styles.reasons}>
        {reasons.map((r, i) => {
          const pct = insurerMode && r.insurer_pct != null ? r.insurer_pct : r.market_pct;
          const marketPct = r.market_pct ?? 0;
          const insurerPct = r.insurer_pct ?? null;
          const showBoth = insurerMode && insurerPct != null;

          return (
            <div key={r.code || i} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div className={styles.reasonLabel}>{r.label}</div>
              <div className={styles.barRow}>
                <div className={styles.barTrack}>
                  {/* Market bar (background) */}
                  <div
                    style={{
                      position: 'absolute',
                      left: 0,
                      top: 0,
                      bottom: 0,
                      width: `${(marketPct / maxPct) * 100}%`,
                      backgroundColor: showBoth ? 'transparent' : COLORS.blue,
                      border: showBoth ? `2px solid ${COLORS.blue}` : 'none',
                      borderRadius: 3,
                      boxSizing: 'border-box',
                    }}
                  />
                  {/* Insurer bar (overlay when both) */}
                  {showBoth && (
                    <div
                      style={{
                        position: 'absolute',
                        left: 0,
                        top: 0,
                        bottom: 0,
                        width: `${(insurerPct / maxPct) * 100}%`,
                        backgroundColor: COLORS.magenta,
                        borderRadius: 3,
                      }}
                    />
                  )}
                </div>
                <span className={styles.barPct}>
                  {((pct ?? 0) * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
