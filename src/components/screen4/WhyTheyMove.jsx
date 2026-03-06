import { useState, useEffect } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import { getReasons } from '../../api';
import ReasonChart from './ReasonChart';
import Placeholder from '../shared/Placeholder';
import {
  proxyReasonsForShopping,
  proxyReasonsForNotShopping,
  proxyReasonsForSwitching,
  getSegmentCounts,
} from '../../utils/measures/whyTheyMoveMeasures';
import styles from './WhyTheyMove.module.css';

const SECTIONS = [
  {
    key: 'shopping',
    title: 'Why Customers Shop (Q8)',
    questionGroup: 'reasons-for-shopping',
    proxyFn: proxyReasonsForShopping,
    placeholderText: 'Additional survey response data to display detailed reasons',
  },
  {
    key: 'switching',
    title: 'Why They Switched (Q31)',
    questionGroup: 'reasons-for-switching',
    proxyFn: proxyReasonsForSwitching,
    placeholderText: 'Additional survey response data to display detailed reasons',
  },
  {
    key: 'not-shopping',
    title: "Why Customers Don't Shop (Q19)",
    questionGroup: 'reasons-for-not-shopping',
    proxyFn: proxyReasonsForNotShopping,
    placeholderText: 'Additional survey response data to display detailed reasons',
  },
];

export default function WhyTheyMove() {
  const { filteredData, selectedInsurer, mode, product } = useDashboard();
  const insurerMode = mode === 'insurer' && selectedInsurer;

  const [apiData, setApiData] = useState({});
  const [apiError, setApiError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setApiError(false);
    const load = async () => {
      const settled = await Promise.allSettled(
        SECTIONS.map(s =>
          getReasons({
            product: product || 'motor',
            brand: insurerMode ? selectedInsurer : null,
            questionGroup: s.questionGroup,
          }).then(res => ({ key: s.key, res }))
        )
      );
      if (cancelled) return;
      const results = {};
      for (const outcome of settled) {
        if (outcome.status === 'fulfilled') {
          const { key, res } = outcome.value;
          if (res?.reasons?.length) {
            results[key] = { reasons: res.reasons, base_n: res.base_n };
          }
        } else {
          setApiError(true);
        }
      }
      setApiData(results);
    };
    load();
    return () => { cancelled = true; };
  }, [insurerMode, selectedInsurer, product]);

  return (
    <div className={styles.container}>
      <h2 className={styles.heading}>Why They Move</h2>
      <p className={styles.subtitle}>
        Reasons behind shopping, switching, and not shopping. Actionable insight for insurers.
      </p>

      <div className={styles.grid}>
        {SECTIONS.map((section) => {
          const apiResult = apiData[section.key];
          const proxyReasons = section.proxyFn(filteredData);
          const segmentCounts = getSegmentCounts(filteredData, insurerMode ? selectedInsurer : null);

          let content;
          if (apiResult?.reasons?.length) {
            content = (
              <ReasonChart
                title={section.title}
                reasons={apiResult.reasons}
                baseN={apiResult.base_n}
                insurerMode={!!insurerMode}
              />
            );
          } else if (proxyReasons?.length && apiError) {
            content = (
              <ReasonChart
                title={`${section.title} (proxy)`}
                reasons={proxyReasons}
                baseN={segmentCounts[section.key]}
                insurerMode={!!insurerMode}
              />
            );
          } else {
            content = (
              <Placeholder
                title={section.title}
                dataNeeded={section.placeholderText}
              />
            );
          }

          return <div key={section.key}>{content}</div>;
        })}
      </div>
    </div>
  );
}
