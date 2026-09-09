// Shared risk color/band helpers.
export function riskColor(score) {
  if (score >= 75) return '#f87171'; // red
  if (score >= 60) return '#fb923c'; // orange
  if (score >= 40) return '#fbbf24'; // amber
  return '#34d399'; // green
}

export function riskBand(score) {
  if (score >= 75) return 'CRITICAL';
  if (score >= 60) return 'HIGH';
  if (score >= 40) return 'ELEVATED';
  return 'LOW';
}

export function severityColor(sev) {
  return {
    CRITICAL: '#f87171',
    HIGH: '#fb923c',
    MEDIUM: '#fbbf24',
    LOW: '#34d399',
  }[sev] || '#8b98ab';
}

export const CRIME_COLORS = {
  UPI_FRAUD: '#22d3ee',
  BANKING_FRAUD: '#a78bfa',
  PHISHING: '#fbbf24',
  SOCIAL_ENGINEERING: '#fb923c',
  INVESTMENT_SCAM: '#f472b6',
  SIM_SWAP: '#f87171',
  ROMANCE_SCAM: '#34d399',
  CASH_ON_DELIVERY_FRAUD: '#38bdf8',
};
export function crimeColor(cat) {
  return CRIME_COLORS[cat] || '#8b98ab';
}

export const ENTITY_COLORS = {
  ATM: '#22d3ee',
  ACCOUNT: '#a78bfa',
  PHONE: '#fbbf24',
  BANK: '#34d399',
  DISTRICT: '#fb923c',
};
export function entityColor(t) {
  return ENTITY_COLORS[t] || '#8b98ab';
}