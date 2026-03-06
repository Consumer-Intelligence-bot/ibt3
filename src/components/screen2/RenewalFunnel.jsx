import { useMemo, useEffect } from 'react';
import {
  ReactFlow,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  MarkerType,
  Background,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { buildShoppingJourneyData } from '../../utils/measures/renewalJourneyMeasures';
import { checkSuppression } from '../../utils/governance';
import { COLORS, FONT } from '../../utils/brandConstants';
import { formatGap } from '../../utils/formatters';

const TREND_ARROW = { up: '▲', down: '▼', flat: '—' };

// Layout constants: 1400x800 canvas, explicit grid
const CANVAS_W = 1400;
const CANVAS_H = 800;
const MARGIN = 20;

const COL_LEFT_X = 40;
const COL_MID_X = 490;
const COL_RIGHT_A_X = 940;
const COL_RIGHT_B_X = 1170;

const NODE_W_WIDE = 340;
const NODE_W_NARROW = 165;
const NODE_H = 90;
const OUTCOME_W_A = 220;
const OUTCOME_W_B = 210;
const OUTCOME_H_TALL = 130;
const OUTCOME_H_SHORT = 110;
const OUTCOME_H_SUMMARY = 120;

const ROW_1_Y = 290;
const ROW_2_Y = 410;
const ROW_3_Y = 520;
const ROW_4_Y = 640;

const RIGHT_WON_FROM_Y = 290;
const RIGHT_RETAINED_Y = 430;
const RIGHT_LOST_TO_Y = 500;
const RIGHT_SUMMARY_Y = 560;

const LEFT_CARD_Y = 480;
const LEFT_CARD_W = 260;
const LEFT_CARD_H = 120;

// Stage header widths (for alignment with columns)
const STAGE_LEFT_W = 300;
const STAGE_MID_W = 500;
const STAGE_RIGHT_W = 440;
const STAGE_GAP = 80;

function getSemanticColor(metricKey, value, marketValue, count, insurerMode) {
  const supp = checkSuppression(count ?? 0);
  if (!supp.show) return COLORS.lightGrey;

  if (!insurerMode) {
    if (metricKey === 'pre-renewal') return COLORS.yellow;
    return '#B8E4F0';
  }

  if (metricKey === 'pre-renewal') return COLORS.yellow;

  const processKeys = ['new-biz', 'non-shoppers', 'shoppers', 'shop-stay', 'shop-switch'];
  if (processKeys.includes(metricKey)) return '#B8E4F0';

  const delta = value != null && marketValue != null ? value - marketValue : null;
  if (delta === null) return '#B8E4F0';

  const favourableHigher = ['retained', 'after-renewal', 'pre-renewal'];
  const favourableLower = ['shop-switch'];
  const isGood =
    favourableHigher.includes(metricKey) ? delta > 0 :
    favourableLower.includes(metricKey) ? delta < 0 :
    delta > 0;
  return isGood ? COLORS.green : COLORS.red;
}

function FunnelBoxNode({ data }) {
  const {
    label,
    pct,
    count,
    semanticColor,
    marketPct,
    delta,
    insurerMode,
    compact,
    isOutcome,
  } = data;

  const pctStr = pct != null ? `${(pct * 100).toFixed(1)}%` : '—';
  const supp = checkSuppression(count ?? 0);
  const showMarket = insurerMode && marketPct != null && delta != null && supp.show;
  const trend = showMarket && delta !== 0 ? (delta > 0 ? 'up' : 'down') : 'flat';

  return (
    <div className="nodrag" style={{ minWidth: 140 }}>
      <Handle type="target" position={Position.Left} style={{ left: 0, visibility: 'hidden' }} />
      <div
        style={{
          backgroundColor: semanticColor,
          borderRadius: isOutcome ? 8 : compact ? 6 : 8,
          padding: compact ? 8 : 12,
          fontFamily: FONT.family,
          border: '1px solid rgba(0,0,0,0.08)',
          boxShadow: isOutcome ? '0 2px 6px rgba(0,0,0,0.06)' : '0 1px 3px rgba(0,0,0,0.08)',
        }}
      >
        <div style={{ fontSize: 11, fontWeight: 600, color: COLORS.darkGrey, marginBottom: 4, letterSpacing: '0.3px' }}>{label}</div>
        <div style={{ fontSize: isOutcome ? 16 : 14, fontWeight: 'bold', color: '#111' }}>{pctStr}</div>
        {count != null && (
          <div style={{ fontSize: 10, color: '#666', marginTop: 2 }}>n={count.toLocaleString()}</div>
        )}
        {showMarket && (
          <div style={{ fontSize: 11, color: COLORS.grey, marginTop: 4 }}>
            (Market: {(marketPct * 100).toFixed(1)}%){' '}
            <span
              style={{
                color: delta > 0 ? COLORS.green : delta < 0 ? COLORS.red : COLORS.grey,
                fontWeight: 'bold',
              }}
            >
              {TREND_ARROW[trend]} {delta === 0 ? '—' : formatGap(delta, 'pct')}
            </span>
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Right} style={{ right: 0, visibility: 'hidden' }} />
    </div>
  );
}

function OutcomeListNode({ data }) {
  const { label, items, borderColor, backgroundColor, showMarket } = data;

  return (
    <div className="nodrag" style={{ minWidth: 140 }}>
      <Handle type="target" position={Position.Left} style={{ left: 0, visibility: 'hidden' }} />
      <div
        style={{
          backgroundColor: backgroundColor || '#FAFAFA',
          borderRadius: 8,
          padding: 10,
          border: '1px solid rgba(0,0,0,0.06)',
          borderLeft: `6px solid ${borderColor}`,
          boxShadow: '0 2px 6px rgba(0,0,0,0.06)',
          fontFamily: FONT.family,
        }}
      >
        <div style={{ fontSize: 11, fontWeight: 600, color: COLORS.darkGrey, marginBottom: 6, letterSpacing: '0.3px' }}>{label}</div>
        {items?.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {items.map(({ brand, pct, marketPct }) => (
              <div
                key={brand}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: 11,
                  fontWeight: 'bold',
                  color: '#111',
                }}
              >
                <span>{brand}</span>
                <span>
                  {(pct * 100).toFixed(1)}
                  {showMarket && marketPct != null ? ` (${(marketPct * 100).toFixed(1)})` : ''}%
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 11, color: '#666' }}>—</div>
        )}
      </div>
      <Handle type="source" position={Position.Right} style={{ right: 0, visibility: 'hidden' }} />
    </div>
  );
}

function SummaryMergeNode({ data }) {
  const { afterRenewal, customerBase, semanticColor, insurerMode } = data;
  const pctStr = afterRenewal.pct != null ? `${(afterRenewal.pct * 100).toFixed(1)}%` : '—';
  const supp = checkSuppression(afterRenewal.count ?? 0);
  const showMarket = insurerMode && afterRenewal.marketPct != null && afterRenewal.delta != null && supp.show;
  const trend = showMarket && afterRenewal.delta !== 0 ? (afterRenewal.delta > 0 ? 'up' : 'down') : 'flat';

  return (
    <div className="nodrag" style={{ width: OUTCOME_W_B, minHeight: OUTCOME_H_SUMMARY }}>
      <Handle type="target" position={Position.Left} style={{ left: 0, visibility: 'hidden' }} />
      <div
        style={{
          backgroundColor: semanticColor,
          borderRadius: 8,
          padding: 10,
          border: '1px solid rgba(0,0,0,0.08)',
          boxShadow: '0 2px 6px rgba(0,0,0,0.06)',
          fontFamily: FONT.family,
        }}
      >
        <div style={{ fontSize: 11, fontWeight: 600, color: COLORS.darkGrey, marginBottom: 4, letterSpacing: '0.3px' }}>
          After renewal market share
        </div>
        <div style={{ fontSize: 16, fontWeight: 'bold', color: '#111' }}>{pctStr}</div>
        {afterRenewal.count != null && (
          <div style={{ fontSize: 10, color: '#666', marginTop: 2 }}>n={afterRenewal.count.toLocaleString()}</div>
        )}
        {showMarket && (
          <div style={{ fontSize: 11, color: COLORS.grey, marginTop: 4 }}>
            (Market: {(afterRenewal.marketPct * 100).toFixed(1)}%){' '}
            <span
              style={{
                color: afterRenewal.delta > 0 ? COLORS.green : afterRenewal.delta < 0 ? COLORS.red : COLORS.grey,
                fontWeight: 'bold',
              }}
            >
              {TREND_ARROW[trend]} {afterRenewal.delta === 0 ? '—' : formatGap(afterRenewal.delta, 'pct')}
            </span>
          </div>
        )}
        <div style={{ fontSize: 11, color: '#444', marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(0,0,0,0.06)' }}>
          Retained {(customerBase.retained * 100).toFixed(1)}% · New business {(customerBase.newBusiness * 100).toFixed(1)}%
        </div>
      </div>
      <Handle type="source" position={Position.Right} style={{ right: 0, visibility: 'hidden' }} />
    </div>
  );
}

/** After Renewal node with embedded composition list (Non Shoppers, Retained, Switched Into) */
function AfterRenewalEmbeddedNode({ data }) {
  const { afterRenewal, composition, semanticColor, insurerMode } = data;
  const pctStr = afterRenewal.pct != null ? `${(afterRenewal.pct * 100).toFixed(1)}%` : '—';
  const supp = checkSuppression(afterRenewal.count ?? 0);
  const showMarket = insurerMode && afterRenewal.marketPct != null && supp.show;

  return (
    <div className="nodrag" style={{ minWidth: 200 }}>
      <Handle type="target" position={Position.Left} style={{ left: 0, visibility: 'hidden' }} />
      <div
        style={{
          backgroundColor: semanticColor || '#E0F2F7',
          borderRadius: 8,
          padding: 12,
          border: '1px solid rgba(0,0,0,0.08)',
          boxShadow: '0 2px 6px rgba(0,0,0,0.06)',
          fontFamily: FONT.family,
        }}
      >
        <div style={{ fontSize: 11, fontWeight: 600, color: COLORS.darkGrey, marginBottom: 4, letterSpacing: '0.3px' }}>
          {afterRenewal.label}
        </div>
        <div style={{ fontSize: 16, fontWeight: 'bold', color: '#111' }}>{afterRenewal.count?.toLocaleString() ?? '—'}</div>
        {showMarket && (
          <div style={{ fontSize: 11, color: COLORS.grey, marginTop: 2 }}>
            {pctStr} (Market: {(afterRenewal.marketPct * 100).toFixed(1)}%)
          </div>
        )}
        {composition && (
          <div style={{ fontSize: 11, color: '#444', marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(0,0,0,0.08)', display: 'flex', flexDirection: 'column', gap: 2 }}>
            {Object.values(composition).map(({ label, pct, marketPct }) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{label}</span>
                <span>{(pct * 100).toFixed(1)}{marketPct != null ? ` (${(marketPct * 100).toFixed(1)})` : ''}%</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Right} style={{ right: 0, visibility: 'hidden' }} />
    </div>
  );
}

const nodeTypes = {
  funnelBox: FunnelBoxNode,
  outcomeList: OutcomeListNode,
  summaryMerge: SummaryMergeNode,
  afterRenewalEmbedded: AfterRenewalEmbeddedNode,
};

// Shopping Journey layout positions
const SJ_ROW_1_Y = 80;   // Before Renewal, Non Shoppers
const SJ_ROW_2_Y = 220;  // Shoppers, Switched From, Quote Channel
const SJ_ROW_3_Y = 360;  // Retained, Purchase from
const SJ_ROW_4_Y = 500;  // After Renewal, Switched Into, Purchase into
const SJ_LEFT_X = 40;
const SJ_MID_X = 380;
const SJ_RIGHT_X = 720;
const SJ_CHANNEL_W = 200;

function buildNodesAndEdges(journey, insurerMode) {
  if (!journey) return { nodes: [], edges: [] };

  const { beforeRenewal, shoppers, nonShoppers, retained, switchedFrom, switchedInto, afterRenewal, quoteChannels, purchaseChannelsInto, purchaseChannelsFrom } = journey;
  const flows = journey.flows || [];

  const getColor = (key, metric) =>
    getSemanticColor(
      key,
      metric?.pct,
      metric?.marketPct,
      metric?.count,
      insurerMode
    );

  const nodes = [
    // Middle column: main flow
    {
      id: 'before-renewal',
      type: 'funnelBox',
      position: { x: SJ_MID_X, y: SJ_ROW_1_Y },
      data: { ...beforeRenewal, semanticColor: getColor('pre-renewal', beforeRenewal), insurerMode },
      draggable: false,
      style: { width: NODE_W_WIDE },
    },
    {
      id: 'shoppers',
      type: 'funnelBox',
      position: { x: SJ_MID_X, y: SJ_ROW_2_Y },
      data: { ...shoppers, semanticColor: getColor('shoppers', shoppers), insurerMode },
      draggable: false,
      style: { width: NODE_W_WIDE },
    },
    {
      id: 'retained',
      type: 'funnelBox',
      position: { x: SJ_MID_X, y: SJ_ROW_3_Y },
      data: { ...retained, semanticColor: getColor('retained', retained), insurerMode, isOutcome: true },
      draggable: false,
      style: { width: NODE_W_WIDE },
    },
    {
      id: 'after-renewal',
      type: 'afterRenewalEmbedded',
      position: { x: SJ_MID_X, y: SJ_ROW_4_Y },
      data: {
        afterRenewal,
        composition: afterRenewal.composition,
        semanticColor: getColor('after-renewal', afterRenewal),
        insurerMode,
      },
      draggable: false,
      style: { width: NODE_W_WIDE },
    },
    // Right column: Non Shoppers, Switched From, Purchase from
    {
      id: 'non-shoppers',
      type: 'funnelBox',
      position: { x: SJ_RIGHT_X, y: SJ_ROW_1_Y },
      data: { ...nonShoppers, semanticColor: getColor('non-shoppers', nonShoppers), insurerMode },
      draggable: false,
      style: { width: OUTCOME_W_B },
    },
    {
      id: 'switched-from',
      type: 'funnelBox',
      position: { x: SJ_RIGHT_X, y: SJ_ROW_2_Y },
      data: { ...switchedFrom, semanticColor: getColor('shop-switch', switchedFrom), insurerMode, isOutcome: true },
      draggable: false,
      style: { width: OUTCOME_W_B },
    },
    {
      id: 'purchase-from',
      type: 'outcomeList',
      position: { x: SJ_RIGHT_X, y: SJ_ROW_3_Y },
      data: {
        label: 'Purchase channels used to switch from ' + (journey.insurer || 'market'),
        items: purchaseChannelsFrom?.map((c) => ({ brand: c.brand, pct: c.pct, marketPct: c.marketPct })) || [],
        borderColor: COLORS.red,
        backgroundColor: '#FFF8F8',
        showMarket: insurerMode,
      },
      draggable: false,
      style: { width: SJ_CHANNEL_W, minHeight: OUTCOME_H_TALL },
    },
    // Left column: Quote Channel, Purchase into, Switched Into
    {
      id: 'quote-channel',
      type: 'outcomeList',
      position: { x: SJ_LEFT_X, y: SJ_ROW_2_Y },
      data: {
        label: 'Quote Channel Multiple',
        items: quoteChannels?.map((c) => ({ brand: c.brand, pct: c.pct, marketPct: c.marketPct })) || [],
        borderColor: COLORS.blue,
        backgroundColor: '#F0F9FF',
        showMarket: insurerMode,
      },
      draggable: false,
      style: { width: SJ_CHANNEL_W, minHeight: OUTCOME_H_TALL },
    },
    {
      id: 'purchase-into',
      type: 'outcomeList',
      position: { x: SJ_LEFT_X, y: SJ_ROW_3_Y },
      data: {
        label: 'Purchase channels used to switch into ' + (journey.insurer || 'market'),
        items: purchaseChannelsInto?.map((c) => ({ brand: c.brand, pct: c.pct, marketPct: c.marketPct })) || [],
        borderColor: COLORS.green,
        backgroundColor: '#F8FAFA',
        showMarket: insurerMode,
      },
      draggable: false,
      style: { width: SJ_CHANNEL_W, minHeight: OUTCOME_H_TALL },
    },
    {
      id: 'switched-into',
      type: 'funnelBox',
      position: { x: SJ_LEFT_X, y: SJ_ROW_4_Y },
      data: {
        ...switchedInto,
        label: switchedInto.label,
        pct: null,
        count: switchedInto.count,
        semanticColor: getColor('new-biz', { count: switchedInto.count }),
        insurerMode,
      },
      draggable: false,
      style: { width: SJ_CHANNEL_W },
    },
  ];

  const nodeIds = new Set(nodes.map((n) => n.id));
  const drawableFlows = flows.filter((f) => f.count > 0 && nodeIds.has(f.from) && nodeIds.has(f.to));

  const edges = drawableFlows.map(({ from, to, count }, i) => ({
    id: `e-${from}-${to}-${i}`,
    source: from,
    target: to,
    type: 'default',
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed },
    style: {
      stroke: COLORS.grey,
      strokeWidth: Math.max(2, Math.min(6, 2 + (count / 200) * 0.5)),
    },
  }));

  return { nodes, edges };
}

export default function RenewalFunnel({ data, insurer, channels }) {
  const journey = useMemo(
    () => buildShoppingJourneyData(data, insurer, channels),
    [data, insurer, channels]
  );

  const { nodes: initialNodes, edges: initialEdges } = useMemo(
    () => buildNodesAndEdges(journey, !!insurer),
    [journey, insurer]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    const { nodes: n, edges: e } = buildNodesAndEdges(journey, !!insurer);
    setNodes(n);
    setEdges(e);
  }, [journey, insurer, setNodes, setEdges]);

  if (!journey) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: '#999', fontFamily: FONT.family }}>
        No funnel data available.
      </div>
    );
  }

  const diagramWidth = CANVAS_W;
  const diagramHeight = CANVAS_H;

  return (
    <div style={{ fontFamily: FONT.family, maxWidth: diagramWidth + 40 }}>
      {/* Stage headers - same width as diagram for alignment */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `${STAGE_LEFT_W}px ${STAGE_GAP}px ${STAGE_MID_W}px ${STAGE_GAP}px ${STAGE_RIGHT_W}px`,
          gap: 0,
          marginBottom: 8,
          width: diagramWidth,
        }}
      >
        <div
          style={{
            fontSize: 10,
            fontWeight: 'bold',
            color: COLORS.grey,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            padding: '6px 0',
            backgroundColor: COLORS.lightGrey,
            borderRadius: 4,
            textAlign: 'center',
          }}
        >
          Channels
        </div>
        <div />
        <div
          style={{
            fontSize: 10,
            fontWeight: 'bold',
            color: COLORS.grey,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            padding: '6px 0',
            backgroundColor: COLORS.lightGrey,
            borderRadius: 4,
            textAlign: 'center',
          }}
        >
          Shopping Journey
        </div>
        <div />
        <div
          style={{
            fontSize: 10,
            fontWeight: 'bold',
            color: COLORS.grey,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            padding: '6px 0',
            backgroundColor: COLORS.lightGrey,
            borderRadius: 4,
            textAlign: 'center',
          }}
        >
          Outcomes
        </div>
      </div>

      <div
        style={{
          width: diagramWidth,
          height: diagramHeight,
          border: '1px solid #E5E7EB',
          borderRadius: 8,
          overflow: 'hidden',
          backgroundColor: '#FAFBFC',
        }}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          minZoom={0.5}
          maxZoom={1.2}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag={true}
          zoomOnScroll={true}
          zoomOnPinch={true}
          preventScrolling={true}
        >
          <Background variant="dots" gap={16} size={1} color="#E5E7EB" style={{ opacity: 0.5 }} />
        </ReactFlow>
      </div>

      <div style={{ fontSize: 12, color: '#666', marginTop: 12 }}>
        Total: {journey.total.toLocaleString()} respondents
        {insurer && journey.insurerTotal != null && (
          <> · {insurer}: {journey.insurerTotal.toLocaleString()}</>
        )}
        <span style={{ marginLeft: 16, color: COLORS.grey, fontSize: 11 }}>Brackets (...) = Market</span>
      </div>
    </div>
  );
}
