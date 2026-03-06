import { useMemo } from 'react';
import { COLORS } from '../../utils/brandConstants';
import styles from './FunnelIndicator.module.css';

/**
 * Three horizontal bars representing the customer journey funnel.
 * Props:
 *   data        array   The filtered data rows
 *   activeStage "renewals" | "shoppers" | "switchers"
 *   insurer     string | null   Filter to insurer if set
 */
export default function FunnelIndicator({ data, activeStage, insurer }) {
  const counts = useMemo(() => {
    const rows = insurer
      ? data.filter(r => r.CurrentCompany === insurer)
      : data;

    const allRenewals = rows.length;
    const shoppers = rows.filter(r => r.Shoppers === 'Shoppers').length;
    const switchers = rows.filter(r => r.Switchers === 'Switcher').length;

    return { allRenewals, shoppers, switchers };
  }, [data, insurer]);

  const stages = [
    { key: 'renewals', label: 'All Renewals', count: counts.allRenewals },
    { key: 'shoppers', label: 'Shoppers', count: counts.shoppers },
    { key: 'switchers', label: 'Switchers', count: counts.switchers },
  ];

  const maxCount = counts.allRenewals || 1;

  return (
    <div className={styles.container}>
      {stages.map(stage => {
        const isActive = stage.key === activeStage;
        const widthPct = Math.round((stage.count / maxCount) * 100);
        const color = isActive ? COLORS.magenta : COLORS.grey;
        const fillColor = isActive ? COLORS.magenta : '#bbb';

        return (
          <div key={stage.key} className={styles.stage}>
            <div className={styles.stageHeader}>
              <span style={{ color, fontWeight: isActive ? 'bold' : 'normal' }}>
                {stage.label}
              </span>
              <span style={{ color, fontWeight: isActive ? 'bold' : 'normal' }}>
                {stage.count.toLocaleString('en-GB')}
              </span>
            </div>
            <div className={styles.track}>
              <div
                className={styles.fill}
                style={{ width: `${widthPct}%`, backgroundColor: fillColor }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
