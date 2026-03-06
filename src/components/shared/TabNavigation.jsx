import { NavLink } from 'react-router-dom';
import { COLORS, FONT } from '../../utils/brandConstants';

const TABS = [
  { label: 'Market Pulse',         path: '/' },
  { label: 'The Renewal Journey',  path: '/renewal-journey' },
  { label: 'Renewal Flow',         path: '/renewal-flow' },
  { label: 'Who Shops, Who Stays', path: '/who-shops-who-stays' },
  { label: 'Why They Move',        path: '/why-they-move' },
  { label: 'Brand Lens',           path: '/brand-lens' },
];

export default function TabNavigation() {
  return (
    <nav style={{
      backgroundColor: '#fff',
      borderBottom: '1px solid #e0e0e0',
      display: 'flex',
    }}>
      {TABS.map(tab => (
        <NavLink
          key={tab.path}
          to={tab.path}
          end={tab.path === '/'}
          style={({ isActive }) => ({
            padding: '12px 24px',
            fontSize: '14px',
            fontFamily: FONT.family,
            color: isActive ? COLORS.magenta : COLORS.grey,
            textDecoration: 'none',
            borderBottom: isActive ? `3px solid ${COLORS.magenta}` : '3px solid transparent',
            fontWeight: isActive ? 'bold' : 'normal',
            whiteSpace: 'nowrap',
            transition: 'color 0.15s, border-bottom-color 0.15s',
            flex: 1,
            textAlign: 'center',
          })}
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
