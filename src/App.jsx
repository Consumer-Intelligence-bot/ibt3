import { useEffect } from 'react';
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
import ValidationPage from './components/shared/ValidationPage';
import { runValidation } from './utils/validation';
import { FONT, COLORS } from './utils/brandConstants';

function AppContent() {
  const { loading, error, rawData } = useDashboard();

  // TODO: REMOVE BEFORE DELIVERY — Ctrl+Shift+V runs validation and logs to console
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'V' && e.ctrlKey && e.shiftKey) {
        e.preventDefault();
        const data = rawData?.length ? rawData : [];
        const results = runValidation(data);
        console.table(results.map(r => ({ ...r, pass: r.pass ? '✓' : '✗' })));
        console.log('Validation:', results.filter(r => !r.pass).length ? 'some failures' : 'all pass');
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [rawData]);

  if (loading) {
    return (
      <div style={{ padding: 40, fontFamily: FONT.family, fontSize: FONT.body }}>
        Loading data…
      </div>
    );
  }
  if (error) {
    return (
      <div style={{ padding: 40, fontFamily: FONT.family, fontSize: FONT.body, color: COLORS.red }}>
        Error: {error}
      </div>
    );
  }

  return (
    <>
      {/* Sticky shell: header + tabs scroll away together */}
      <div style={{ position: 'sticky', top: 0, zIndex: 100 }}>
        <Header />
        <TabNavigation />
      </div>

      <main style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
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
          {/* TODO: REMOVE BEFORE DELIVERY — dev-only validation route */}
          <Route path="/validation" element={<ValidationPage />} />
        </Routes>
      </main>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <DashboardProvider>
        <AppContent />
      </DashboardProvider>
    </BrowserRouter>
  );
}
