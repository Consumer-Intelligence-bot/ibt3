import { COLORS, FONT } from '../../utils/brandConstants';
import { formatPct } from '../../utils/formatters';

const fmtPctOrSuppressed = (v) => v != null ? formatPct(v) : 'n<30';

function BreakdownRow({ label, insValue, mktValue }) {
  return (
    <div style={{ marginBottom: 4 }}>
      <span style={{ fontSize: 12, color: '#4D5153', minWidth: 120, display: 'inline-block' }}>{label}</span>
      <span style={{ fontSize: 12, fontWeight: 'bold', color: COLORS.magenta, minWidth: 60, display: 'inline-block' }}>
        {fmtPctOrSuppressed(insValue)}
      </span>
      <span style={{ fontSize: 11, color: COLORS.grey }}>
        Mkt {fmtPctOrSuppressed(mktValue)}
      </span>
    </div>
  );
}

function SourceRow({ rank, brand, pct }) {
  return (
    <div style={{ marginBottom: 4 }}>
      <span style={{ fontSize: 12, color: '#4D5153', minWidth: 140, display: 'inline-block' }}>
        {rank}. {brand}
      </span>
      <span style={{ fontSize: 12, fontWeight: 'bold', color: COLORS.magenta }}>
        {fmtPctOrSuppressed(pct)}
      </span>
    </div>
  );
}

export default function DeepDivePanel({ metric, isOpen, deepDiveData, insurerName }) {
  if (!isOpen || !deepDiveData) return null;

  const panelStyle = {
    backgroundColor: '#FAFAFA', borderRadius: 6,
    padding: 16, marginTop: 8,
    borderLeft: `3px solid ${COLORS.magenta}`,
    fontFamily: FONT.family,
    overflow: 'hidden',
    transition: 'max-height 0.3s ease, opacity 0.3s ease',
  };

  const headingStyle = { fontSize: 12, fontWeight: 'bold', marginBottom: 8, color: '#4D5153' };

  const renderShoppingDeepDive = () => (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <div>
        <div style={headingStyle}>By premium change</div>
        {(deepDiveData.shopByPremium || []).map(r => (
          <BreakdownRow key={r.label} label={r.label} insValue={r.insurer} mktValue={r.market} />
        ))}
      </div>
      <div>
        <div style={headingStyle}>By age group</div>
        {(deepDiveData.shopByAge || []).map(r => (
          <BreakdownRow key={r.label} label={r.label} insValue={r.insurer} mktValue={r.market} />
        ))}
      </div>
    </div>
  );

  const renderRetentionDeepDive = () => (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <div>
        <div style={headingStyle}>By premium change</div>
        {(deepDiveData.retByPremium || []).map(r => (
          <BreakdownRow key={r.label} label={r.label} insValue={r.insurer} mktValue={r.market} />
        ))}
      </div>
      <div>
        <div style={headingStyle}>By region</div>
        {(deepDiveData.retByRegion || []).map(r => (
          <BreakdownRow key={r.label} label={r.label} insValue={r.insurer} mktValue={r.market} />
        ))}
      </div>
    </div>
  );

  const renderShopStayDeepDive = () => (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <div>
        <div style={headingStyle}>Premium change split</div>
        {(deepDiveData.shopStayByPremium || []).map(r => (
          <BreakdownRow key={r.label} label={r.label} insValue={r.insurer} mktValue={r.market} />
        ))}
      </div>
      <div>
        <div style={headingStyle}>PCW usage</div>
        {deepDiveData.shopStayPcw ? (
          <>
            <BreakdownRow label={insurerName} insValue={deepDiveData.shopStayPcw.insurer} mktValue={null} />
            <BreakdownRow label="Market" insValue={deepDiveData.shopStayPcw.market} mktValue={null} />
          </>
        ) : (
          <div style={{ fontSize: 11, color: COLORS.grey, fontStyle: 'italic' }}>Insufficient data</div>
        )}
      </div>
    </div>
  );

  const renderNewBizDeepDive = () => (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <div>
        <div style={headingStyle}>Top source brands</div>
        {(deepDiveData.newBizSources || []).map((s, i) => (
          <SourceRow key={s.brand} rank={i + 1} brand={s.brand} pct={s.pct} />
        ))}
      </div>
      <div>
        <div style={headingStyle}>Channel</div>
        {deepDiveData.newBizChannel ? (
          <>
            <BreakdownRow label="PCW" insValue={deepDiveData.newBizChannel.insurer} mktValue={deepDiveData.newBizChannel.market} />
            <BreakdownRow label="Direct / Other" insValue={1 - deepDiveData.newBizChannel.insurer} mktValue={1 - deepDiveData.newBizChannel.market} />
          </>
        ) : (
          <div style={{ fontSize: 11, color: COLORS.grey, fontStyle: 'italic' }}>Insufficient data</div>
        )}
      </div>
    </div>
  );

  const renderers = {
    shopping: renderShoppingDeepDive,
    retention: renderRetentionDeepDive,
    shoppedAndStayed: renderShopStayDeepDive,
    newBiz: renderNewBizDeepDive,
  };

  const render = renderers[metric];
  if (!render) return null;

  return <div style={panelStyle}>{render()}</div>;
}
