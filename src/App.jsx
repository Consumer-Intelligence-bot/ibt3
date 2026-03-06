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
import HeadlinePage from './components/headline/HeadlinePage';
import ErrorBoundary from './components/shared/ErrorBoundary';
import { FONT, COLORS } from './utils/brandConstants';

function AppContent() {
  const { loading, error } = useDashboard();

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
              <HeadlinePage />
            </ScreenLayout>
          } />
          <Route path="/market-pulse" element={
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
