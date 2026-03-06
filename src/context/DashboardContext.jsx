import { createContext, useContext, useState, useEffect, useMemo } from 'react';
import { loadCSV } from '../utils/loadCSV';
import { addDerivedFields } from '../utils/deriveFields';
import { THRESHOLDS } from '../utils/brandConstants';

const DashboardContext = createContext(null);

const DEFAULT_CONFIG = {
  motorFile: 'motor_main_data_demo.csv',
  homeFile: 'all home data.csv',
};

export function DashboardProvider({ children }) {
  const [rawDataMotor, setRawDataMotor] = useState([]);
  const [rawDataHome, setRawDataHome] = useState([]);
  const [mode, setMode] = useState('market');
  const [selectedInsurer, setSelectedInsurer] = useState(null);
  const [product, setProduct] = useState('motor');
  const [timeWindow, setTimeWindow] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load config.json then both data files (from server startup script or defaults)
  useEffect(() => {
    let config = DEFAULT_CONFIG;
    fetch(`${import.meta.env.BASE_URL}config.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((c) => {
        if (c?.motorFile && c?.homeFile) config = c;
        return Promise.all([
          loadCSV(config.motorFile).catch(() => []),
          loadCSV(config.homeFile).catch(() => []),
        ]);
      })
      .then(([motorRows, homeRows]) => {
        setRawDataMotor(addDerivedFields(motorRows));
        setRawDataHome(addDerivedFields(homeRows));
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const rawData = product === 'motor' ? rawDataMotor : rawDataHome;

  const filterByTimeWindow = (data) => {
    if (!data?.length) return [];
    if (timeWindow === 'all') return data;
    const months = timeWindow === '12m' ? 12 : 24;
    const allMonths = [...new Set(data.map((r) => r.RenewalYearMonth))].sort((a, b) => b - a);
    const cutoffMonths = allMonths.slice(0, months);
    return data.filter((r) => cutoffMonths.includes(r.RenewalYearMonth));
  };

  const filteredData = useMemo(() => filterByTimeWindow(rawData), [rawData, timeWindow]);
  const filteredDataMotor = useMemo(() => filterByTimeWindow(rawDataMotor), [rawDataMotor, timeWindow]);
  const filteredDataHome = useMemo(() => filterByTimeWindow(rawDataHome), [rawDataHome, timeWindow]);

  // Build insurer list (those meeting publishable threshold)
  const insurerList = useMemo(() => {
    const counts = {};
    filteredData.forEach(row => {
      const name = row.CurrentCompany;
      if (name) counts[name] = (counts[name] || 0) + 1;
    });

    return Object.entries(counts)
      .filter(([_, count]) => count >= THRESHOLDS.publishable)
      .map(([name]) => name)
      .sort();
  }, [filteredData]);

  const value = {
    rawData,
    filteredData,
    filteredDataMotor,
    filteredDataHome,
    mode,
    setMode,
    selectedInsurer,
    setSelectedInsurer,
    product,
    setProduct,
    timeWindow,
    setTimeWindow,
    insurerList,
    loading,
    error,
  };

  return (
    <DashboardContext.Provider value={value}>
      {children}
    </DashboardContext.Provider>
  );
}

export function useDashboard() {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error('useDashboard must be used within DashboardProvider');
  return ctx;
}
