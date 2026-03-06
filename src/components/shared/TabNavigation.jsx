import { NavLink } from 'react-router-dom';
import styles from './TabNavigation.module.css';

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
    <nav className={styles.nav}>
      {TABS.map(tab => (
        <NavLink
          key={tab.path}
          to={tab.path}
          end={tab.path === '/'}
          className={({ isActive }) => isActive ? styles.tabActive : styles.tab}
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
