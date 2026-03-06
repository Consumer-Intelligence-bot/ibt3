import { useMemo, useRef, useEffect, useState } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import { buildFunnelData } from '../../utils/measures/renewalJourneyMeasures';
import { formatPct } from '../../utils/formatters';
import { COLORS, FONT } from '../../utils/brandConstants';

const FLOW_COLORS = {
  green: COLORS.green,
  red: COLORS.red,
  blue: COLORS.blue,
  magenta: COLORS.magenta,
  orange: COLORS.yellow,
  grey: COLORS.grey,
  lightGrey: COLORS.lightGrey,
  white: COLORS.white,
  darkGrey: COLORS.darkGrey,
};

const PHASE_BG = {
  pre: '#ECEDF2',
  renewal: COLORS.white,
  post: '#E8F3EA',
};

function FlowCard({ title, value, benchmark, color, icon, style, children }) {
  const borderColor = color === FLOW_COLORS.green ? '#B8DFC0'
    : color === FLOW_COLORS.red ? '#F0B8B8'
    : color === FLOW_COLORS.blue ? '#B8D4EF'
    : color === FLOW_COLORS.magenta ? '#D4A8D3'
    : color === FLOW_COLORS.orange ? '#F0D7A0'
    : '#D8DCE3';

  const bgTint = color === FLOW_COLORS.green ? '#F8FCF9'
    : color === FLOW_COLORS.red ? '#FDF5F5'
    : color === FLOW_COLORS.blue ? '#F5F9FD'
    : color === FLOW_COLORS.magenta ? '#FBF5FB'
    : color === FLOW_COLORS.orange ? '#FFFCF5'
    : COLORS.white;

  return (
    <div style={{
      position: 'absolute',
      background: bgTint,
      borderRadius: 7,
      padding: '7px 10px',
      textAlign: 'center',
      boxShadow: '0 2px 8px rgba(0,0,0,0.10)',
      border: `1.5px solid ${borderColor}`,
      fontFamily: FONT.family,
      zIndex: 3,
      ...style,
    }}>
      {icon && <div style={{ fontSize: 18, marginBottom: 2 }}>{icon}</div>}
      <div style={{
        fontSize: 9.5,
        fontWeight: 600,
        lineHeight: 1.2,
        marginBottom: 2,
        color,
      }}>{title}</div>
      {value !== undefined && (
        <div style={{
          fontFamily: FONT.family,
          fontSize: 14,
          fontWeight: 700,
          color,
        }}>{value}</div>
      )}
      {benchmark !== undefined && (
        <div style={{ fontSize: 9, color: FLOW_COLORS.grey }}>({benchmark})</div>
      )}
      {children}
    </div>
  );
}

function OutlineCard({ title, value, style }) {
  return (
    <div style={{
      position: 'absolute',
      background: 'transparent',
      borderRadius: 7,
      padding: '7px 10px',
      textAlign: 'center',
      border: `2.5px solid ${FLOW_COLORS.green}`,
      fontFamily: FONT.family,
      zIndex: 3,
      ...style,
    }}>
      <div style={{
        fontSize: 9.5,
        fontWeight: 600,
        lineHeight: 1.2,
        marginBottom: 2,
        color: FLOW_COLORS.green,
      }}>{title}</div>
      <div style={{
        fontFamily: FONT.family,
        fontSize: 20,
        fontWeight: 700,
        color: FLOW_COLORS.green,
      }}>{value}</div>
    </div>
  );
}

function BrandList({ title, brands, color, style }) {
  const borderColor = color === FLOW_COLORS.green ? '#B8DFC0' : '#F0B8B8';
  const bgTint = color === FLOW_COLORS.green ? '#F8FCF9' : '#FDF5F5';

  return (
    <div style={{
      position: 'absolute',
      background: bgTint,
      borderRadius: 7,
      padding: '7px 10px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.10)',
      border: `1.5px solid ${borderColor}`,
      fontFamily: FONT.family,
      zIndex: 3,
      ...style,
    }}>
      <div style={{
        fontSize: 9.5,
        fontWeight: 600,
        color,
        marginBottom: 4,
      }}>
        {title} <span style={{ fontWeight: 400, color: FLOW_COLORS.grey }}>(top 3)</span>
      </div>
      {brands.map((b) => (
        <div key={b.brand} style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 9,
          padding: '1.5px 0',
          gap: 8,
        }}>
          <span style={{ color: FLOW_COLORS.grey }}>{b.brand}</span>
          <span style={{ fontWeight: 700, color }}>{formatPct(b.pct)}</span>
        </div>
      ))}
    </div>
  );
}

function IconCircle({ emoji, bg, style }) {
  return (
    <div style={{
      position: 'absolute',
      width: 36,
      height: 36,
      borderRadius: '50%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: 16,
      background: bg,
      zIndex: 2,
      ...style,
    }}>{emoji}</div>
  );
}

function FlowArrows() {
  return (
    <svg
      style={{ position: 'absolute', top: 0, left: 0, width: 860, height: 500, zIndex: 1, pointerEvents: 'none' }}
      viewBox="0 0 860 500"
    >
      <defs>
        <marker id="ma" markerWidth="6" markerHeight="5" refX="6" refY="2.5" orient="auto">
          <polygon points="0 0,6 2.5,0 5" fill="#c0c5cd" />
        </marker>
        <marker id="mg" markerWidth="6" markerHeight="5" refX="6" refY="2.5" orient="auto">
          <polygon points="0 0,6 2.5,0 5" fill={COLORS.green} />
        </marker>
        <marker id="mr" markerWidth="6" markerHeight="5" refX="6" refY="2.5" orient="auto">
          <polygon points="0 0,6 2.5,0 5" fill={COLORS.red} />
        </marker>
      </defs>

      {/* Pre: envelope → people */}
      <line x1="77" y1="110" x2="77" y2="160" strokeDasharray="4,3" stroke="#c0c5cd" strokeWidth="1.4" fill="none" markerEnd="url(#ma)" />
      {/* Pre: people → question */}
      <line x1="77" y1="215" x2="77" y2="255" strokeDasharray="4,3" stroke="#c0c5cd" strokeWidth="1.4" fill="none" markerEnd="url(#ma)" />
      {/* Pre: question → right */}
      <line x1="102" y1="280" x2="155" y2="280" stroke="#c0c5cd" strokeWidth="1.4" fill="none" markerEnd="url(#ma)" />

      {/* Split up to non-shoppers */}
      <path d="M 172 268 C 200 268, 218 200, 245 200" stroke="#c0c5cd" strokeWidth="1.4" fill="none" markerEnd="url(#ma)" />
      {/* Split down to shoppers */}
      <path d="M 172 292 C 200 292, 218 368, 245 368" stroke="#c0c5cd" strokeWidth="1.4" fill="none" markerEnd="url(#ma)" />

      {/* New biz from left */}
      <line x1="160" y1="92" x2="252" y2="92" stroke="#c0c5cd" strokeWidth="1.4" fill="none" markerEnd="url(#ma)" />

      {/* Non-shoppers → retained */}
      <path d="M 365 200 C 430 200, 470 255, 548 255" stroke={COLORS.green} strokeWidth="1.4" fill="none" markerEnd="url(#mg)" />

      {/* Shoppers → stayed */}
      <path d="M 365 358 C 388 358, 398 305, 410 305" stroke="#c0c5cd" strokeWidth="1.4" fill="none" markerEnd="url(#ma)" />
      {/* Shoppers → switched */}
      <path d="M 365 378 C 388 378, 398 418, 410 418" stroke="#c0c5cd" strokeWidth="1.4" fill="none" markerEnd="url(#ma)" />

      {/* Stayed → retained */}
      <path d="M 520 305 C 533 305, 538 265, 548 265" stroke={COLORS.green} strokeWidth="1.4" fill="none" markerEnd="url(#mg)" />

      {/* Switched → lost */}
      <path d="M 520 418 C 533 418, 538 408, 548 408" stroke={COLORS.red} strokeWidth="1.4" fill="none" markerEnd="url(#mr)" />

      {/* New biz → won from */}
      <line x1="382" y1="88" x2="548" y2="88" stroke={COLORS.green} strokeWidth="1.4" fill="none" markerEnd="url(#mg)" />

      {/* Won from → after mkt share */}
      <path d="M 692 95 C 718 95, 722 155, 723 165" stroke={COLORS.green} strokeWidth="1.4" fill="none" markerEnd="url(#mg)" />

      {/* Retained → after mkt share */}
      <path d="M 682 260 C 718 260, 722 205, 723 195" stroke={COLORS.green} strokeWidth="1.4" fill="none" markerEnd="url(#mg)" />

      {/* After → customer base */}
      <line x1="790" y1="230" x2="790" y2="275" stroke={COLORS.green} strokeWidth="1.4" fill="none" markerEnd="url(#mg)" />
    </svg>
  );
}

function PhaseLabel({ label, color, style }) {
  return (
    <div style={{
      position: 'absolute',
      bottom: 5,
      left: '50%',
      transform: 'translateX(-50%)',
      fontFamily: FONT.family,
      fontSize: 8,
      fontWeight: 700,
      letterSpacing: 1.5,
      textTransform: 'uppercase',
      whiteSpace: 'nowrap',
      color,
      ...style,
    }}>{label}</div>
  );
}

export default function RenewalFlow() {
  const { filteredData, selectedInsurer, mode } = useDashboard();
  const containerRef = useRef(null);
  const [scale, setScale] = useState(1);

  const insurer = mode === 'insurer' ? selectedInsurer : null;

  const funnelData = useMemo(
    () => buildFunnelData(filteredData, insurer),
    [filteredData, insurer],
  );

  useEffect(() => {
    function fitCanvas() {
      if (!containerRef.current) return;
      const availW = containerRef.current.clientWidth;
      setScale(Math.min(1, availW / 860));
    }
    fitCanvas();
    window.addEventListener('resize', fitCanvas);
    return () => window.removeEventListener('resize', fitCanvas);
  }, []);

  if (!filteredData?.length) {
    return (
      <div style={{ padding: 60, textAlign: 'center', color: '#999', fontFamily: FONT.family }}>
        <h2 style={{ fontSize: 24, marginBottom: 12 }}>Renewal Flow</h2>
        <p>No data available. Ensure data is loaded and filters are applied.</p>
      </div>
    );
  }

  if (!funnelData) {
    return (
      <div style={{ padding: 60, textAlign: 'center', color: '#999', fontFamily: FONT.family }}>
        <h2 style={{ fontSize: 24, marginBottom: 12 }}>Renewal Flow</h2>
        <p>Insufficient data for the selected insurer. Try selecting a different insurer or switching to market view.</p>
      </div>
    );
  }

  const d = funnelData;
  const heading = insurer ? `Renewal Flow — ${insurer}` : 'Renewal Flow — Market View';

  return (
    <div style={{ fontFamily: FONT.family }}>
      <h2 style={{ fontSize: 24, marginBottom: 16 }}>{heading}</h2>

      <div
        ref={containerRef}
        style={{
          backgroundColor: COLORS.white,
          borderRadius: 8,
          boxShadow: '0 1px 4px rgba(0,0,0,0.10)',
          overflow: 'hidden',
          height: 500 * scale,
        }}
      >
        <div style={{
          position: 'relative',
          width: 860,
          height: 500,
          transformOrigin: 'top left',
          transform: `scale(${scale})`,
        }}>
          {/* Phase backgrounds */}
          <div style={{ position: 'absolute', top: 0, bottom: 0, left: 0, width: 155, background: PHASE_BG.pre, borderRadius: '8px 0 0 8px' }}>
            <PhaseLabel label="PRE-RENEWAL" color="#8890B8" />
          </div>
          <div style={{ position: 'absolute', top: 0, bottom: 0, left: 155, width: 360, background: PHASE_BG.renewal }}>
            <PhaseLabel label="RENEWAL" color="#BBB" />
          </div>
          <div style={{ position: 'absolute', top: 0, bottom: 0, left: 515, width: 345, background: PHASE_BG.post, borderRadius: '0 8px 8px 0' }}>
            <PhaseLabel label="POST-RENEWAL" color={COLORS.green} />
          </div>

          <FlowArrows />

          {/* PRE-RENEWAL icons */}
          <IconCircle emoji="✉" bg="#DCE5F0" style={{ top: 72, left: 60 }} />
          <IconCircle emoji="👥" bg="#EDE7F6" style={{ top: 168, left: 60 }} />
          <IconCircle emoji="❓" bg="#FFF3E0" style={{ top: 260, left: 60, fontSize: 13 }} />

          {/* Pre-renewal market share */}
          <OutlineCard
            title={<>Pre-renewal<br />market share</>}
            value={formatPct(d.preRenewalShare.pct)}
            style={{ top: 355, left: 12, width: 130 }}
          />

          {/* RENEWAL cards */}
          <FlowCard
            title={<>New business<br />acquisition</>}
            value={formatPct(d.newBusiness.pct)}
            benchmark={d.newBusiness.marketPct !== undefined ? formatPct(d.newBusiness.marketPct) : undefined}
            color={FLOW_COLORS.magenta}
            icon="👤+"
            style={{ top: 50, left: 255, width: 118 }}
          />

          <FlowCard
            title="Non-shoppers"
            value={formatPct(d.nonShoppers.pct)}
            benchmark={d.nonShoppers.marketPct !== undefined ? formatPct(d.nonShoppers.marketPct) : undefined}
            color={FLOW_COLORS.blue}
            icon="📞"
            style={{ top: 155, left: 230, width: 118 }}
          />

          <FlowCard
            title="Shoppers"
            value={formatPct(d.shoppers.pct)}
            benchmark={d.shoppers.marketPct !== undefined ? formatPct(d.shoppers.marketPct) : undefined}
            color={FLOW_COLORS.orange}
            icon="🛒"
            style={{ top: 325, left: 230, width: 118 }}
          />

          <FlowCard
            title={<>Shopped then<br />stayed</>}
            value={formatPct(d.shoppers.shopStay.pct)}
            benchmark={d.shoppers.shopStay.marketPct !== undefined ? formatPct(d.shoppers.shopStay.marketPct) : undefined}
            color={FLOW_COLORS.green}
            icon="💚"
            style={{ top: 260, left: 410, width: 108 }}
          />

          <FlowCard
            title={<>Shopped then<br />switched</>}
            value={formatPct(d.shoppers.shopSwitch.pct)}
            benchmark={d.shoppers.shopSwitch.marketPct !== undefined ? formatPct(d.shoppers.shopSwitch.marketPct) : undefined}
            color={FLOW_COLORS.red}
            icon="🔄"
            style={{ top: 382, left: 410, width: 108 }}
          />

          {/* POST-RENEWAL cards */}
          {d.wonFrom && d.wonFrom.breakdown?.length > 0 && (
            <BrandList
              title="Won from"
              brands={d.wonFrom.breakdown}
              color={FLOW_COLORS.green}
              style={{ top: 40, left: 550, width: 140 }}
            />
          )}

          <FlowCard
            title="Retained"
            value={formatPct(d.retained.pct)}
            benchmark={d.retained.marketPct !== undefined ? formatPct(d.retained.marketPct) : undefined}
            color={FLOW_COLORS.green}
            icon="✅"
            style={{ top: 210, left: 550, width: 125 }}
          />

          <FlowCard
            title={<>After renewal<br />market share</>}
            value={formatPct(d.afterRenewalShare.pct)}
            color={FLOW_COLORS.green}
            icon="👥"
            style={{ top: 148, left: 725, width: 125 }}
          >
            {d.afterRenewalShare.delta !== undefined && d.afterRenewalShare.delta !== 0 && (
              <span style={{
                display: 'inline-block',
                fontSize: 9,
                fontWeight: 700,
                padding: '1px 6px',
                borderRadius: 8,
                background: d.afterRenewalShare.delta > 0 ? '#D4EDDA' : '#FDDEDE',
                color: d.afterRenewalShare.delta > 0 ? COLORS.green : COLORS.red,
                marginTop: 2,
              }}>
                {d.afterRenewalShare.delta > 0 ? '+' : ''}{(d.afterRenewalShare.delta * 100).toFixed(1)}%
              </span>
            )}
          </FlowCard>

          {/* Customer base */}
          <div style={{
            position: 'absolute',
            top: 280,
            left: 725,
            width: 125,
            background: COLORS.white,
            borderRadius: 7,
            padding: '7px 10px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.10)',
            border: '1.5px solid #D8DCE3',
            fontFamily: FONT.family,
            zIndex: 3,
          }}>
            <div style={{ fontSize: 9.5, fontWeight: 600, color: FLOW_COLORS.darkGrey, marginBottom: 4 }}>
              Customer base
            </div>
            <div style={{ display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: `${(d.customerBase.retained * 100)}%`, background: COLORS.green }} />
              <div style={{ width: `${(d.customerBase.newBusiness * 100)}%`, background: COLORS.blue }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3, fontSize: 7.5, color: FLOW_COLORS.grey }}>
              <span>
                <span style={{ display: 'inline-block', width: 5, height: 5, borderRadius: '50%', background: COLORS.green, marginRight: 2, verticalAlign: 'middle' }} />
                Ret. {formatPct(d.customerBase.retained)}
              </span>
              <span>
                <span style={{ display: 'inline-block', width: 5, height: 5, borderRadius: '50%', background: COLORS.blue, marginRight: 2, verticalAlign: 'middle' }} />
                New {formatPct(d.customerBase.newBusiness)}
              </span>
            </div>
          </div>

          {d.lostTo && d.lostTo.breakdown?.length > 0 && (
            <BrandList
              title="Lost to"
              brands={d.lostTo.breakdown}
              color={FLOW_COLORS.red}
              style={{ top: 375, left: 550, width: 140 }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
