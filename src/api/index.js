/**
 * API client for Shopping & Switching Dashboard.
 * Switches between mockApi and realApi based on VITE_USE_MOCKS.
 * @see docs/api-contract.md
 */

const useMocks = import.meta.env.VITE_USE_MOCKS === 'true';

let _api = null;

async function getApi() {
  if (_api) return _api;
  _api = useMocks
    ? await import('./mockApi.js').then(m => m.mockApi)
    : await import('./realApi.js');
  return _api;
}

export const getKpis = (...args) => getApi().then(api => api.getKpis(...args));
export const getReasons = (...args) => getApi().then(api => api.getReasons(...args));
export const getTrends = (...args) => getApi().then(api => api.getTrends(...args));
export const getFlows = (...args) => getApi().then(api => api.getFlows(...args));
export const getChannels = (...args) => getApi().then(api => api.getChannels(...args));
export const getComparison = (...args) => getApi().then(api => api.getComparison(...args));
export const requestExport = (...args) => getApi().then(api => api.requestExport(...args));
