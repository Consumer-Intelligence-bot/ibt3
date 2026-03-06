import { useState, useRef, useEffect } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import { THRESHOLDS } from '../../utils/brandConstants';
import styles from './Header.module.css';

const PERIOD_OPTIONS = [
  { value: 'all', label: 'All data' },
  { value: '12m', label: 'Last 12 months' },
  { value: '24m', label: 'Last 24 months' },
];

export default function Header() {
  const {
    mode, setMode,
    selectedInsurer, setSelectedInsurer,
    product, setProduct,
    timeWindow, setTimeWindow,
    insurerList,
  } = useDashboard();

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [searchText, setSearchText] = useState('');
  const dropdownRef = useRef(null);

  // Close insurer dropdown when clicking outside
  useEffect(() => {
    function handleOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  function handleModeChange(newMode) {
    setMode(newMode);
    if (newMode === 'market') {
      setSelectedInsurer(null);
    }
    setDropdownOpen(false);
    setSearchText('');
  }

  function handleInsurerSelect(name) {
    setSelectedInsurer(name);
    setDropdownOpen(false);
    setSearchText('');
  }

  // Filtered list for the searchable dropdown
  const lowerSearch = searchText.toLowerCase();
  const filteredPublished = insurerList.filter(n => n.toLowerCase().includes(lowerSearch));

  return (
    <div className={styles.header}>
      {/* Logo row */}
      <div className={styles.logoRow}>
        <div className={styles.logoTitle}>Consumer Intelligence</div>
        <div className={styles.logoSubtitle}>Shopping &amp; Switching</div>
      </div>

      {/* Controls row */}
      <div className={styles.controls}>

        {/* Market / Insurer toggle */}
        <ToggleGroup>
          <ToggleBtn active={mode === 'market'} onClick={() => handleModeChange('market')}>
            Market
          </ToggleBtn>
          <ToggleBtn active={mode === 'insurer'} onClick={() => handleModeChange('insurer')}>
            Insurer
          </ToggleBtn>
        </ToggleGroup>

        {/* Insurer dropdown — insurer mode only */}
        {mode === 'insurer' && (
          <div ref={dropdownRef} style={{ position: 'relative' }}>
            <button
              onClick={() => setDropdownOpen(prev => !prev)}
              className={styles.dropdownTrigger}
            >
              <span className={styles.dropdownTriggerLabel}>
                {selectedInsurer || 'Select insurer…'}
              </span>
              <span className={styles.chevron}>▾</span>
            </button>

            {dropdownOpen && (
              <div className={styles.dropdownPanel}>
                {/* Search */}
                <div className={styles.searchBox}>
                  <input
                    autoFocus
                    value={searchText}
                    onChange={e => setSearchText(e.target.value)}
                    placeholder="Search insurers…"
                    className={styles.searchInput}
                  />
                </div>

                {/* List body */}
                <div className={styles.listBody}>
                  {filteredPublished.length > 0
                    ? filteredPublished.map(name => (
                        <DropdownItem
                          key={name}
                          name={name}
                          selected={name === selectedInsurer}
                          onSelect={handleInsurerSelect}
                        />
                      ))
                    : (
                        <div className={styles.emptyMessage}>
                          No insurers meet the minimum sample size (n ≥ {THRESHOLDS.publishable})
                        </div>
                      )
                  }
                </div>
              </div>
            )}
          </div>
        )}

        {/* Motor / Home toggle */}
        <ToggleGroup>
          <ToggleBtn active={product === 'motor'} onClick={() => setProduct('motor')}>
            Motor
          </ToggleBtn>
          <ToggleBtn active={product === 'home'} onClick={() => setProduct('home')}>
            Home
          </ToggleBtn>
        </ToggleGroup>

        {/* Period selector */}
        <div style={{ position: 'relative' }}>
          <select
            value={timeWindow}
            onChange={e => setTimeWindow(e.target.value)}
            className={styles.periodSelect}
          >
            {PERIOD_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value} className={styles.periodOption}>
                {opt.label}
              </option>
            ))}
          </select>
          <span className={styles.selectChevron}>▾</span>
        </div>

      </div>
    </div>
  );
}

/* ---- Sub-components ---- */

function ToggleGroup({ children }) {
  return (
    <div className={styles.toggleGroup}>{children}</div>
  );
}

function ToggleBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={active ? styles.toggleBtnActive : styles.toggleBtnInactive}
    >
      {children}
    </button>
  );
}

function DropdownItem({ name, selected, onSelect }) {
  return (
    <button
      onClick={() => onSelect(name)}
      className={selected ? styles.dropdownItemSelected : styles.dropdownItem}
    >
      {name}
    </button>
  );
}
