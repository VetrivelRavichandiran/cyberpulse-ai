// CYBERPULSE AI — typed endpoint helpers (thin wrappers over the client).
import { api } from './client';

export const auth = {
  login: (username, password) => api.post('/auth/login', { username, password }),
  me: () => api.get('/auth/me'),
};

export const health = {
  get: () => api.get('/health'),
};

export const dashboard = {
  summary: () => api.get('/dashboard/summary'),
  complaintTrend: (days = 14) => api.get(`/dashboard/complaint-trend?days=${days}`),
  riskTrend: () => api.get('/dashboard/risk-trend'),
  transactionActivity: () => api.get('/dashboard/transaction-activity'),
  alertStatus: () => api.get('/dashboard/alert-status'),
  districtRisk: () => api.get('/dashboard/district-risk'),
  hotspotEvolution: () => api.get('/dashboard/hotspot-evolution'),
};

export const mapApi = {
  complaints: (days = 30, limit = 500) => api.get(`/map/complaints?days=${days}&limit=${limit}`),
  atms: () => api.get('/map/atms'),
  hotspots: () => api.get('/map/hotspots'),
  riskZones: () => api.get('/map/risk-zones'),
  withdrawals: (days = 3, limit = 1000) => api.get(`/map/withdrawals?days=${days}&limit=${limit}`),
  nearby: (lat, lon, radius_km = 5) => api.get(`/map/nearby?lat=${lat}&lon=${lon}&radius_km=${radius_km}`),
};

export const predictions = {
  list: (limit = 100) => api.get(`/predictions?limit=${limit}`),
  hotspots: () => api.get('/predictions/hotspots'),
  get: (id) => api.get(`/predictions/${id}`),
  generate: () => api.post('/predictions/generate', {}),
};

export const alerts = {
  list: (limit = 100, status) => api.get(`/alerts?limit=${limit}${status ? `&status=${status}` : ''}`),
  get: (id) => api.get(`/alerts/${id}`),
  acknowledge: (id) => api.post(`/alerts/${id}/acknowledge`, {}),
  escalate: (id) => api.post(`/alerts/${id}/escalate`, {}),
  resolve: (id) => api.post(`/alerts/${id}/resolve`, {}),
};

export const investigations = {
  list: () => api.get('/investigations'),
  get: (caseId) => api.get(`/investigations/${caseId}`),
  fromAlert: (alertId) => api.post(`/investigations/from-alert/${alertId}`, {}),
  addNote: (caseId, note) => api.post(`/investigations/${caseId}/notes`, { note }),
  addIntervention: (caseId, payload) => api.post(`/investigations/${caseId}/interventions`, payload),
  setStatus: (caseId, status) => api.post(`/investigations/${caseId}/status`, { status }),
  graph: (caseId) => api.get(`/investigations/${caseId}/graph`),
  reportBlob: (caseId) => api.blob(`/investigations/${caseId}/report`),
};

export const graph = {
  stats: () => api.get('/graph/stats'),
  cluster: (entityId, hops = 2) => api.get(`/graph/cluster/${entityId}?hops=${hops}`),
  suspiciousChains: (since_hours = 720) => api.get(`/graph/patterns/suspicious-chains?since_hours=${since_hours}`),
  sharedPhone: () => api.get('/graph/patterns/shared-phone'),
};

export const model = {
  info: () => api.get('/model/info'),
  evaluation: () => api.get('/model/evaluation'),
  featureImportance: () => api.get('/model/feature-importance'),
  shapSummary: () => api.get('/model/shap-summary'),
};

export const simulation = {
  whatIf: (payload) => api.post('/simulation/what-if', payload),
  atms: () => api.get('/simulation/atms'),
};

export const demo = {
  run: () => api.post('/demo/run', {}),
  reset: () => api.post('/demo/reset', {}),
};

export const notifications = {
  list: (limit = 50) => api.get(`/notifications?limit=${limit}`),
  markRead: (id) => api.post(`/notifications/${id}/read`, {}),
};

export const audit = {
  list: (limit = 50) => api.get(`/audit?limit=${limit}`),
};

export const dataApi = {
  complaints: (limit = 100) => api.get(`/data/complaints?limit=${limit}`),
  transactions: (limit = 100) => api.get(`/data/transactions?limit=${limit}`),
  atms: (limit = 100) => api.get(`/data/atms?limit=${limit}`),
  districts: () => api.get('/data/districts'),
};