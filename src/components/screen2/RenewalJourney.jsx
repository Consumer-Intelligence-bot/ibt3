import { useState, useEffect } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import { getChannels } from '../../api';
import RenewalFunnel from './RenewalFunnel';
import styles from './RenewalJourney.module.css';

export default function RenewalJourney() {
  const { filteredData, selectedInsurer, mode, product } = useDashboard();
  const [channels, setChannels] = useState(null);

  const insurer = mode === 'insurer' ? selectedInsurer : null;

  useEffect(() => {
    if (!insurer || !product) {
      setChannels(null);
      return;
    }
    getChannels({ product, brand: insurer })
      .then(setChannels)
      .catch(() => setChannels(null));
  }, [insurer, product]);

  if (!filteredData?.length) {
    return (
      <div className={styles.empty}>
        <h2 className={styles.emptyHeading}>Shopping Journey</h2>
        <p>No flow data available. Ensure data is loaded and filters are applied.</p>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <h2 className={styles.heading}>
        Shopping Journey{insurer ? ` - ${insurer}` : ''}
      </h2>

      <div className={styles.flowWrapper}>
        <RenewalFunnel data={filteredData} insurer={insurer} channels={channels} />
      </div>
    </div>
  );
}
