import styles from './SuppressionMessage.module.css';

/**
 * Displayed when data cannot be shown due to insufficient sample size.
 * Props:
 *   message: string — the reason for suppression (never blank when shown)
 */
export default function SuppressionMessage({ message }) {
  return (
    <div className={styles.container}>
      <p className={styles.title}><strong>Data suppressed</strong></p>
      <p className={styles.detail}>{message || 'Insufficient data for this view.'}</p>
    </div>
  );
}
