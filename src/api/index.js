/**
 * API client for Shopping & Switching Dashboard.
 * Switches between mockApi and realApi based on VITE_USE_MOCKS.
 * @see docs/api-contract.md
 */

const useMocks = import.meta.env.VITE_USE_MOCKS === 'true';

let _apiPromise = null;

function getApi() {
  if (!_apiPromise) {
    _apiPromise = useMocks
      ? import('./mockApi.js').then(m => m.mockApi)
      : import('./realApi.js');
  }
  return _apiPromise;
}

export const getKpis = (...args) => getApi().then(api => api.getKpis(...args));
export const getReasons = (...args) => getApi().then(api => api.getReasons(...args));
export const getTrends = (...args) => getApi().then(api => api.getTrends(...args));
export const getFlows = (...args) => getApi().then(api => api.getFlows(...args));
export const getChannels = (...args) => getApi().then(api => api.getChannels(...args));
export const getComparison = (...args) => getApi().then(api => api.getComparison(...args));
export const requestExport = (...args) => getApi().then(api => api.requestExport(...args));
