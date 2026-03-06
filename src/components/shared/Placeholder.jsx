import styles from './Placeholder.module.css';

/**
 * Placeholder for visuals that require data not yet available.
 * Props:
 *   title       string   What the visual would show
 *   dataNeeded  string   What data file or question is needed
 */
export default function Placeholder({ title, dataNeeded }) {
  return (
    <div className={styles.container}>
      <p className={styles.title}>{title}</p>
      <p className={styles.detail}>{dataNeeded}</p>
    </div>
  );
}
