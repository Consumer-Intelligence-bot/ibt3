import styles from './PlaceholderScreen.module.css';

export default function PlaceholderScreen({ title }) {
  return (
    <div className={styles.container}>
      <h2 className={styles.heading}>{title}</h2>
      <p>This screen will be available when additional data is connected.</p>
    </div>
  );
}
