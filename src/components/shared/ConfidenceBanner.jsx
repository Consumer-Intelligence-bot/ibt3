import { getConfidenceBannerInfo } from '../../utils/governance';
import styles from './ConfidenceBanner.module.css';

/**
 * Full-width confidence banner for insurer mode.
 * Props:
 *   n: number — sample size for selected insurer
 */
export default function ConfidenceBanner({ n }) {
  const { colour, label } = getConfidenceBannerInfo(n);

  return (
    <div className={styles.banner} style={{ backgroundColor: colour }}>
      {label} — based on {n} responses
    </div>
  );
}
