import { useState, useRef, useEffect } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import { COLORS, FONT, THRESHOLDS } from '../../utils/brandConstants';

const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function formatYearMonth(ym) {
  if (!ym) return '';
  const year = Math.floor(ym / 100);
  const month = ym % 100;
  return `${MONTH_NAMES[month - 1] || '???'} ${String(year).slice(-2)}`;
}

export default function Header() {
  const {
    mode, setMode,
    selectedInsurer, setSelectedInsurer,
    product, setProduct,
    availableMonths, selectedMonths, setSelectedMonths,
    insurerList,
  } = useDashboard();

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [searchText, setSearchText] = useState('');
  const dropdownRef = useRef(null);
  const [monthDropdownOpen, setMonthDropdownOpen] = useState(false);
  const monthDropdownRef = useRef(null);

  // Close dropdowns when clicking outside
  useEffect(() => {
    function handleOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
      if (monthDropdownRef.current && !monthDropdownRef.current.contains(e.target)) {
        setMonthDropdownOpen(false);
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

        {/* Month multi-select */}
        <div ref={monthDropdownRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setMonthDropdownOpen(prev => !prev)}
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
              minWidth: '160px',
            }}
          >
            <span style={{ flex: 1, textAlign: 'left' }}>
              {selectedMonths.length === 0
                ? 'Select months...'
                : selectedMonths.length === availableMonths.length
                  ? 'All months'
                  : `${selectedMonths.length} month${selectedMonths.length === 1 ? '' : 's'}`}
            </span>
            <span style={{ fontSize: '10px' }}>▾</span>
          </button>

          {monthDropdownOpen && (
            <div style={{
              position: 'absolute',
              top: 'calc(100% + 4px)',
              right: 0,
              backgroundColor: '#fff',
              border: '1px solid #ddd',
              borderRadius: '4px',
              boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
              zIndex: 200,
              minWidth: '200px',
              maxHeight: '340px',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}>
              {/* Select All / Clear All */}
              <div style={{
                display: 'flex',
                gap: '8px',
                padding: '8px',
                borderBottom: '1px solid #eee',
              }}>
                <button
                  onClick={() => setSelectedMonths([...availableMonths])}
                  style={{
                    flex: 1,
                    padding: '4px 8px',
                    fontSize: '12px',
                    fontFamily: FONT.family,
                    border: '1px solid #ddd',
                    borderRadius: '3px',
                    backgroundColor: '#f5f5f5',
                    cursor: 'pointer',
                    color: '#333',
                  }}
                >
                  Select All
                </button>
                <button
                  onClick={() => setSelectedMonths([])}
                  style={{
                    flex: 1,
                    padding: '4px 8px',
                    fontSize: '12px',
                    fontFamily: FONT.family,
                    border: '1px solid #ddd',
                    borderRadius: '3px',
                    backgroundColor: '#f5f5f5',
                    cursor: 'pointer',
                    color: '#333',
                  }}
                >
                  Clear All
                </button>
              </div>

              {/* Month checklist */}
              <div style={{ overflowY: 'auto', flex: 1 }}>
                {availableMonths.map(ym => {
                  const checked = selectedMonths.includes(ym);
                  return (
                    <label
                      key={ym}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '6px 12px',
                        fontSize: '13px',
                        fontFamily: FONT.family,
                        cursor: 'pointer',
                        color: '#333',
                        backgroundColor: checked ? '#F3E8F3' : 'transparent',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {
                          setSelectedMonths(prev =>
                            checked
                              ? prev.filter(m => m !== ym)
                              : [...prev, ym].sort((a, b) => b - a)
                          );
                        }}
                        style={{ accentColor: COLORS.magenta }}
                      />
                      {formatYearMonth(ym)}
                    </label>
                  );
                })}
              </div>
            </div>
          )}
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
