import { useMemo } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import ConfidenceBanner from './ConfidenceBanner';
import FunnelIndicator from './FunnelIndicator';
import SuppressionMessage from './SuppressionMessage';
import { checkSuppression } from '../../utils/governance';
import styles from './ScreenLayout.module.css';

/**
 * Standard screen layout wrapper.
 * Renders confidence banner (insurer mode), then children, then funnel.
 *
 * Props:
 *   activeStage: "renewals" | "shoppers" | "switchers"
 *   children: screen content
 */
export default function ScreenLayout({ activeStage, children }) {
  const { mode, selectedInsurer, filteredData } = useDashboard();

  const isInsurerWithSelection = mode === 'insurer' && selectedInsurer;

  const { n, suppressionCheck } = useMemo(() => {
    if (!isInsurerWithSelection) {
      return { n: 0, suppressionCheck: { show: true, level: 'publishable', message: null } };
    }
    const count = filteredData.filter(r => r.CurrentCompany === selectedInsurer).length;
    return { n: count, suppressionCheck: checkSuppression(count) };
  }, [isInsurerWithSelection, filteredData, selectedInsurer]);

  return (
    <div>
      {/* Confidence banner — insurer mode only */}
      {isInsurerWithSelection && (
        <div className={styles.bannerWrap}>
          <ConfidenceBanner n={n} />
        </div>
      )}

      {/* Main content or suppression message */}
      {isInsurerWithSelection && !suppressionCheck.show
        ? <SuppressionMessage message={suppressionCheck.message} />
        : children
      }

      {/* Funnel indicator — always visible */}
      <div className={styles.funnelWrap}>
        <FunnelIndicator
          data={filteredData}
          activeStage={activeStage}
          insurer={mode === 'insurer' ? selectedInsurer : null}
        />
      </div>
    </div>
  );
}
