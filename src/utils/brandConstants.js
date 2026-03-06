export const COLORS = {
  magenta: '#981D97',           // CI Violet - Primary accent, insurer data
  grey: '#54585A',              // Market benchmark
  green: '#48A23F',             // CI Green - Positive indicator
  red: '#F4364C',               // CI Red - Negative indicator
  blue: '#5BC2E7',              // CI Blue - Secondary accent
  yellow: '#FFCD00',            // CI Yellow - Highlight / warning
  darkGrey: '#4D5153',          // CI Dark Grey - Text colour
  lightGrey: '#E9EAEB',         // CI Light Grey - Secondary background
  confidenceFill: 'rgba(224, 224, 224, 0.3)', // Confidence band
  white: '#FFFFFF',
  backgroundLight: '#F5F5F5',   // Fallback background (legacy)
};

export const FONT = {
  family: 'Verdana, Geneva, sans-serif',
  cardValue: '32px',            // Spec: Verdana Bold 32pt for KPI value
  cardLabel: '11px',             // Spec: Verdana Regular 11pt for labels
  body: '14px',
  heading: '18px',
};

export const THRESHOLDS = {
  publishable: 50,      // n >= 50: show value
  indicative: 30,       // n >= 30: show with "indicative" label
  minimum: 30,          // n < 30: suppress entirely
};
