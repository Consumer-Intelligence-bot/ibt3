import { useState, useRef, useEffect } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import { COLORS, FONT, THRESHOLDS } from '../../utils/brandConstants';

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
    <div style={{
      backgroundColor: COLORS.magenta,
      padding: '12px 24px',
      boxShadow: '0 2px 6px rgba(0,0,0,0.2)',
    }}>
      {/* Logo row */}
      <div style={{ marginBottom: '10px' }}>
        <div style={{ color: '#fff', fontSize: '16px', fontWeight: 'bold', fontFamily: FONT.family }}>
          Consumer Intelligence
        </div>
        <div style={{ color: 'rgba(255,255,255,0.8)', fontSize: '12px', fontFamily: FONT.family }}>
          Shopping &amp; Switching
        </div>
      </div>

      {/* Controls row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>

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
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 12px',
                backgroundColor: 'rgba(255,255,255,0.15)',
                border: '1px solid rgba(255,255,255,0.45)',
                borderRadius: '4px',
                color: '#fff',
                fontSize: '13px',
                fontFamily: FONT.family,
                cursor: 'pointer',
                minWidth: '180px',
              }}
            >
              <span style={{ flex: 1, textAlign: 'left' }}>
                {selectedInsurer || 'Select insurer…'}
              </span>
              <span style={{ fontSize: '10px' }}>▾</span>
            </button>

            {dropdownOpen && (
              <div style={{
                position: 'absolute',
                top: 'calc(100% + 4px)',
                left: 0,
                backgroundColor: '#fff',
                border: '1px solid #ddd',
                borderRadius: '4px',
                boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
                zIndex: 200,
                minWidth: '240px',
                maxHeight: '340px',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
              }}>
                {/* Search */}
                <div style={{ padding: '8px', borderBottom: '1px solid #eee' }}>
                  <input
                    autoFocus
                    value={searchText}
                    onChange={e => setSearchText(e.target.value)}
                    placeholder="Search insurers…"
                    style={{
                      width: '100%',
                      padding: '6px 10px',
                      border: '1px solid #ddd',
                      borderRadius: '3px',
                      fontSize: '13px',
                      fontFamily: FONT.family,
                      outline: 'none',
                      boxSizing: 'border-box',
                    }}
                  />
                </div>

                {/* List body */}
                <div style={{ overflowY: 'auto', flex: 1 }}>
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
                        <div style={{
                          padding: '10px 16px',
                          fontSize: '12px',
                          color: '#888',
                          fontFamily: FONT.family,
                          fontStyle: 'italic',
                        }}>
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
            style={{
              padding: '6px 32px 6px 12px',
              backgroundColor: 'rgba(255,255,255,0.15)',
              border: '1px solid rgba(255,255,255,0.45)',
              borderRadius: '4px',
              color: '#fff',
              fontSize: '13px',
              fontFamily: FONT.family,
              cursor: 'pointer',
              appearance: 'none',
              WebkitAppearance: 'none',
            }}
          >
            {PERIOD_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value} style={{ backgroundColor: '#fff', color: '#333' }}>
                {opt.label}
              </option>
            ))}
          </select>
          {/* Custom chevron */}
          <span style={{
            position: 'absolute',
            right: '10px',
            top: '50%',
            transform: 'translateY(-50%)',
            fontSize: '10px',
            color: '#fff',
            pointerEvents: 'none',
          }}>
            ▾
          </span>
        </div>

      </div>
    </div>
  );
}

/* ---- Sub-components ---- */

function ToggleGroup({ children }) {
  return (
    <div style={{
      display: 'flex',
      backgroundColor: 'rgba(255,255,255,0.2)',
      borderRadius: '4px',
      padding: '2px',
      alignItems: 'center',
    }}>
      {children}
    </div>
  );
}

function ToggleBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '5px 13px',
        fontSize: '13px',
        fontFamily: FONT.family,
        border: 'none',
        borderRadius: '3px',
        backgroundColor: active ? '#fff' : 'transparent',
        color: active ? COLORS.magenta : 'rgba(255,255,255,0.9)',
        fontWeight: active ? 'bold' : 'normal',
        cursor: 'pointer',
        transition: 'background-color 0.15s, color 0.15s',
      }}
    >
      {children}
    </button>
  );
}

function DropdownItem({ name, selected, onSelect }) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      onClick={() => onSelect(name)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'block',
        width: '100%',
        textAlign: 'left',
        padding: '8px 16px',
        border: 'none',
        backgroundColor: selected ? '#F3E8F3' : hovered ? '#f5f5f5' : 'transparent',
        color: selected ? COLORS.magenta : '#333',
        fontSize: '13px',
        fontFamily: FONT.family,
        cursor: 'pointer',
        fontWeight: selected ? 'bold' : 'normal',
      }}
    >
      {name}
    </button>
  );
}
