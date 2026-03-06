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
  const [selectedMonths, setSelectedMonths] = useState([]); // array of YYYYMM ints
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

  // All unique YYYYMM values from the active product data, sorted descending (newest first)
  const availableMonths = useMemo(() => {
    const all = [...new Set(rawData.map((r) => r.RenewalYearMonth).filter(Boolean))];
    return all.sort((a, b) => b - a);
  }, [rawData]);

  // Default to last 12 months when data loads or product changes
  useEffect(() => {
    if (availableMonths.length > 0) {
      setSelectedMonths(availableMonths.slice(0, 12));
    }
  }, [availableMonths]);

  const filterBySelectedMonths = (data) => {
    if (!data?.length) return [];
    if (!selectedMonths?.length) return data;
    const monthSet = new Set(selectedMonths);
    return data.filter((r) => monthSet.has(r.RenewalYearMonth));
  };

  const filteredData = useMemo(() => filterBySelectedMonths(rawData), [rawData, selectedMonths]);
  const filteredDataMotor = useMemo(() => filterBySelectedMonths(rawDataMotor), [rawDataMotor, selectedMonths]);
  const filteredDataHome = useMemo(() => filterBySelectedMonths(rawDataHome), [rawDataHome, selectedMonths]);

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
    availableMonths,
    selectedMonths,
    setSelectedMonths,
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
