import styles from './NarrativeCard.module.css';

/**
 * NarrativeCard — insurer mode only.
 * Displays auto-generated narrative text with the insurer name bolded.
 * Left border in CI Magenta.
 */
export default function NarrativeCard({ insurer, text }) {
  if (!text || !insurer) return null;

  // Bold every occurrence of the insurer name in the text
  const parts = text.split(insurer);

  return (
    <div className={styles.card}>
      {parts.map((part, i) => (
        <span key={i}>
          {i > 0 && <strong>{insurer}</strong>}
          {part}
        </span>
      ))}
    </div>
  );
}
