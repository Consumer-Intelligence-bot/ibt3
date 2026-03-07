import { useState, useMemo } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import { COLORS, FONT } from '../../utils/brandConstants';
import {
  calcHeadlineMetrics,
  deriveTag,
  calcPremiumChangeComparison,
  calcChannelComparison,
  calcNetMovementRank,
  shoppingRateByPremiumChange,
  shoppingRateByAge,
  retentionByPremiumChange,
  retentionByRegion,
  shopStayByPremiumChange,
  shopStayPCWUsage,
  newBizSourceBrands,
  newBizChannelBreakdown,
} from '../../utils/measures/headlineMeasures';
import ComparisonBar from './ComparisonBar';
import ButterflyChart from './ButterflyChart';
import DeepDivePanel from './DeepDivePanel';
import PremiumChangeVsMarket from './PremiumChangeVsMarket';
import SourceOfBusiness from './SourceOfBusiness';

const fmtPct = (v) => `${(v * 100).toFixed(1)}%`;

function ShareCard({ label, valueStr, colour, borderTop }) {
  const style = {
    backgroundColor: '#FFF', borderRadius: 8,
    boxShadow: '0 1px 4px rgba(0,0,0,0.10)',
    padding: '16px 20px', textAlign: 'center', fontFamily: FONT.family,
  };
  if (borderTop) style.borderTop = `4px solid ${borderTop}`;

  return (
    <div style={style}>
      <div style={{ fontSize: 11, color: '#666', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 36, fontWeight: 'bold', color: colour, lineHeight: '1.1' }}>
        {valueStr}
      </div>
    </div>
  );
}

function RankBadge({ rankData }) {
  if (!rankData) return null;
  const { rank, totalBrands } = rankData;
  const positionPct = ((rank - 1) / Math.max(totalBrands - 1, 1)) * 100;

  let colour, quartile;
  if (rank <= totalBrands * 0.25) { colour = COLORS.green; quartile = 'Top quartile'; }
  else if (rank <= totalBrands * 0.75) { colour = COLORS.grey; quartile = 'Mid range'; }
  else { colour = COLORS.red; quartile = 'Bottom quartile'; }

  return (
    <div style={{
      backgroundColor: '#FFF', borderRadius: 8,
      boxShadow: '0 1px 4px rgba(0,0,0,0.10)',
      padding: '12px 16px', fontFamily: FONT.family, textAlign: 'center', marginTop: 8,
    }}>
      <div style={{ fontSize: 10, color: '#666', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>
        Movement rank
      </div>
      <div style={{ fontSize: 20, fontWeight: 'bold', color: colour, marginBottom: 6 }}>
        #{rank} of {totalBrands}
      </div>
      <div style={{ position: 'relative', height: 10, backgroundColor: COLORS.lightGrey, borderRadius: 5, marginBottom: 4 }}>
        <div style={{
          position: 'absolute', left: `${positionPct.toFixed(0)}%`,
          top: -2, width: 10, height: 14,
          backgroundColor: colour, borderRadius: 3, transform: 'translateX(-50%)',
        }} />
      </div>
      <div style={{ fontSize: 10, color: colour, fontStyle: 'italic' }}>{quartile}</div>
    </div>
  );
}

export default function HeadlinePage() {
  const { filteredData, selectedInsurer } = useDashboard();
  const [openPanels, setOpenPanels] = useState({
    shopping: false, retention: false, shoppedAndStayed: false, newBiz: false,
  });

  const togglePanel = (key) => setOpenPanels(prev => ({ ...prev, [key]: !prev[key] }));

  const metrics = useMemo(() => calcHeadlineMetrics(filteredData, selectedInsurer), [filteredData, selectedInsurer]);
  const pcData = useMemo(() => calcPremiumChangeComparison(filteredData, selectedInsurer), [filteredData, selectedInsurer]);
  const chData = useMemo(() => calcChannelComparison(filteredData, selectedInsurer), [filteredData, selectedInsurer]);
  const rankData = useMemo(() => calcNetMovementRank(filteredData, selectedInsurer), [filteredData, selectedInsurer]);

  // Deep-dive data
  const deepDiveData = useMemo(() => {
    if (!filteredData?.length || !selectedInsurer) return {};
    return {
      shopByPremium: shoppingRateByPremiumChange(filteredData, selectedInsurer),
      shopByAge: shoppingRateByAge(filteredData, selectedInsurer),
      retByPremium: retentionByPremiumChange(filteredData, selectedInsurer),
      retByRegion: retentionByRegion(filteredData, selectedInsurer),
      shopStayByPremium: shopStayByPremiumChange(filteredData, selectedInsurer),
      shopStayPcw: shopStayPCWUsage(filteredData, selectedInsurer),
      newBizSources: newBizSourceBrands(filteredData, selectedInsurer),
      newBizChannel: newBizChannelBreakdown(filteredData, selectedInsurer),
    };
  }, [filteredData, selectedInsurer]);

  if (!selectedInsurer) {
    return (
      <div style={{ padding: '40px 0', textAlign: 'center', fontFamily: FONT.family }}>
        <h2 style={{ color: '#4D5153' }}>Headline</h2>
        <p style={{ color: COLORS.grey, fontSize: 14 }}>Select an insurer to view the headline story.</p>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div style={{ padding: '40px 0', textAlign: 'center', fontFamily: FONT.family }}>
        <p style={{ color: COLORS.grey, fontSize: 14 }}>Insufficient data for the selected filters.</p>
      </div>
    );
  }

  const ins = metrics.insurer;
  const prePp = metrics.preShare * 100;
  const postPp = metrics.afterShare * 100;
  const deltaPp = metrics.shareDelta * 100;
  const deltaSign = deltaPp >= 0 ? '+' : '';
  const movementColour = deltaPp > 0 ? COLORS.green : (deltaPp < 0 ? COLORS.red : COLORS.grey);

  const shopTag = deriveTag(metrics.shopPct, metrics.mktShopPct);
  const retTag = deriveTag(metrics.retainedPct, metrics.mktRetainedPct);
  const stayTag = deriveTag(metrics.shopStayPct, metrics.mktShopStayPct);
  const bizTag = deriveTag(metrics.newBizPct, metrics.mktNewBizPct);

  const direction = deltaPp > 0 ? 'lifting' : (deltaPp < 0 ? 'dropping' : 'holding');
  const support = `Retention and acquisition both beat market, ${direction} share from ${prePp.toFixed(1)}% to ${postPp.toFixed(1)}% through renewal.`;

  // Butterfly callout
  const wonBrands = new Set(metrics.wonFrom.map(w => w.brand));
  const lostBrands = new Set(metrics.lostTo.map(l => l.brand));
  const overlap = [...wonBrands].filter(b => lostBrands.has(b) && b !== 'New to market');
  let callout = null;
  if (overlap.length > 0) {
    const topBattle = overlap.sort((a, b) => {
      const aPct = metrics.lostTo.find(l => l.brand === a)?.pct || 0;
      const bPct = metrics.lostTo.find(l => l.brand === b)?.pct || 0;
      return bPct - aPct;
    })[0];
    callout = `${topBattle} is the main two-way battleground.`;
  } else if (metrics.wonFrom.length > 0) {
    callout = `Largest source: ${metrics.wonFrom[0].brand}.`;
  }

  return (
    <div style={{ fontFamily: FONT.family, maxWidth: 900, margin: '0 auto' }}>
      {/* Headline */}
      <h1 style={{ fontSize: 22, fontWeight: 'bold', color: '#4D5153', margin: '0 0 6px', lineHeight: '1.3' }}>
        Customers shop at the market rate, but {ins} keeps more of them
      </h1>
      <p style={{ fontSize: 14, color: COLORS.grey, margin: '0 0 20px', lineHeight: '1.5' }}>
        {support}
      </p>

      {/* Outcome: 3-column grid (KPI card + sub-card) */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 32, justifyContent: 'center', flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 260px', maxWidth: 280 }}>
          <ShareCard label="Pre-renewal share" valueStr={`${prePp.toFixed(1)}%`} colour="#4D5153" />
          <PremiumChangeVsMarket insurer={pcData?.insurer} market={pcData?.market} />
        </div>
        <div style={{ flex: '1 1 260px', maxWidth: 280 }}>
          <ShareCard
            label="Net movement"
            valueStr={`${deltaSign}${deltaPp.toFixed(1)} pts`}
            colour={movementColour}
            borderTop={movementColour}
          />
          <RankBadge rankData={rankData} />
        </div>
        <div style={{ flex: '1 1 260px', maxWidth: 280 }}>
          <ShareCard label="Post-renewal share" valueStr={`${postPp.toFixed(1)}%`} colour={COLORS.magenta} />
          <SourceOfBusiness insurer={chData?.insurer} market={chData?.market} />
        </div>
      </div>

      {/* Why this happened */}
      <div style={{
        backgroundColor: '#FFF', borderRadius: 8,
        boxShadow: '0 1px 4px rgba(0,0,0,0.10)',
        padding: 20, marginBottom: 32,
      }}>
        <div style={{ fontSize: 15, fontWeight: 'bold', color: '#4D5153', marginBottom: 4 }}>
          Why this happened
        </div>
        <p style={{ fontSize: 13, color: COLORS.grey, margin: '0 0 20px', lineHeight: '1.5' }}>
          Customers are just as likely to shop around. {ins} performs better when they do.
        </p>

        {/* Shopping rate */}
        <div style={{ marginBottom: 16 }}>
          <ComparisonBar
            label="Shopping rate" insValue={metrics.shopPct} mktValue={metrics.mktShopPct}
            tag={shopTag} insurerName={ins} onClickMore={() => togglePanel('shopping')}
          />
          <DeepDivePanel metric="shopping" isOpen={openPanels.shopping} deepDiveData={deepDiveData} insurerName={ins} />
        </div>

        {/* Retention */}
        <div style={{ marginBottom: 16 }}>
          <ComparisonBar
            label="Retention" insValue={metrics.retainedPct} mktValue={metrics.mktRetainedPct}
            tag={retTag} insurerName={ins} onClickMore={() => togglePanel('retention')}
          />
          <DeepDivePanel metric="retention" isOpen={openPanels.retention} deepDiveData={deepDiveData} insurerName={ins} />
        </div>

        {/* Shopped and stayed */}
        <div style={{ marginBottom: 16 }}>
          <ComparisonBar
            label="Shopped and stayed" insValue={metrics.shopStayPct} mktValue={metrics.mktShopStayPct}
            tag={stayTag} insurerName={ins} onClickMore={() => togglePanel('shoppedAndStayed')}
          />
          <DeepDivePanel metric="shoppedAndStayed" isOpen={openPanels.shoppedAndStayed} deepDiveData={deepDiveData} insurerName={ins} />
        </div>

        {/* New business acquisition */}
        <div style={{ marginBottom: 16 }}>
          <ComparisonBar
            label="New business acquisition" insValue={metrics.newBizPct} mktValue={metrics.mktNewBizPct}
            tag={bizTag} insurerName={ins}
            maxVal={Math.max(metrics.newBizPct, metrics.mktNewBizPct) * 2.5 || 0.01}
            onClickMore={() => togglePanel('newBiz')}
          />
          <DeepDivePanel metric="newBiz" isOpen={openPanels.newBiz} deepDiveData={deepDiveData} insurerName={ins} />
        </div>
      </div>

      {/* Competitive exchange */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ fontSize: 15, fontWeight: 'bold', color: '#4D5153', marginBottom: 12 }}>
          Competitive exchange
        </div>
        <ButterflyChart wonFrom={metrics.wonFrom} lostTo={metrics.lostTo} callout={callout} />
      </div>

      {/* Footer */}
      <div style={{ fontSize: 11, color: COLORS.grey, textAlign: 'center', paddingBottom: 24 }}>
        Base: {metrics.n.toLocaleString()} respondents
      </div>
    </div>
  );
}
