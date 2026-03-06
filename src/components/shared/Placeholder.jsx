import { FONT } from '../../utils/brandConstants';

/**
 * Placeholder for visuals that require data not yet available.
 * Props:
 *   title       string   What the visual would show
 *   dataNeeded  string   What data file or question is needed
 */
export default function Placeholder({ title, dataNeeded }) {
  return (
    <div style={{
      border: '2px dashed #ccc',
      borderRadius: '8px',
      backgroundColor: '#f9f9f9',
      minHeight: '250px',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
      fontFamily: FONT.family,
      textAlign: 'center',
    }}>
      <p style={{ fontWeight: 'bold', fontSize: '14px', color: '#555', margin: '0 0 8px' }}>
        {title}
      </p>
      <p style={{ fontSize: '12px', color: '#999', margin: 0 }}>
        {dataNeeded}
      </p>
    </div>
  );
}
