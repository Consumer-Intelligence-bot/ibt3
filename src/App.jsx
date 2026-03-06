import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { DashboardProvider, useDashboard } from './context/DashboardContext';
import Header from './components/shared/Header';
import TabNavigation from './components/shared/TabNavigation';
import PlaceholderScreen from './components/shared/PlaceholderScreen';
import RenewalJourney from './components/screen2/RenewalJourney';
import WhyTheyMove from './components/screen4/WhyTheyMove';
import ScreenLayout from './components/shared/ScreenLayout';
import MarketPulse from './components/screen1/MarketPulse';
import ShopOrStay from './components/screen2/ShopOrStay';
import RenewalFlow from './components/screen2/RenewalFlow';
import ErrorBoundary from './components/shared/ErrorBoundary';
import styles from './App.module.css';

function AppContent() {
  const { loading, error } = useDashboard();

  if (loading) {
    return <div className={styles.loading}>Loading data…</div>;
  }
  if (error) {
    return <div className={styles.error}>Error: {error}</div>;
  }

  return (
    <>
      <div className={styles.stickyShell}>
        <Header />
        <TabNavigation />
      </div>

      <main className={styles.main}>
        <Routes>
          <Route path="/" element={
            <ScreenLayout activeStage="renewals">
              <MarketPulse />
            </ScreenLayout>
          } />
          <Route path="/renewal-journey" element={
            <ScreenLayout activeStage="renewals">
              <RenewalJourney />
            </ScreenLayout>
          } />
          <Route path="/renewal-flow" element={
            <ScreenLayout activeStage="renewals">
              <RenewalFlow />
            </ScreenLayout>
          } />
          <Route path="/who-shops-who-stays" element={
            <ScreenLayout activeStage="shoppers">
              <ShopOrStay />
            </ScreenLayout>
          } />
          <Route path="/why-they-move" element={
            <ScreenLayout activeStage="switchers">
              <WhyTheyMove />
            </ScreenLayout>
          } />
          <Route path="/brand-lens" element={<PlaceholderScreen title="Brand Lens" />} />
        </Routes>
      </main>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <DashboardProvider>
        <ErrorBoundary>
          <AppContent />
        </ErrorBoundary>
      </DashboardProvider>
    </BrowserRouter>
  );
}
