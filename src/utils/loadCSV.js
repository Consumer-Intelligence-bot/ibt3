import Papa from 'papaparse';
import { normaliseColumns } from './normaliseColumns';

/**
 * Load and parse a CSV file from the public/data folder.
 * Returns normalised rows with typed values.
 */
export async function loadCSV(filename) {
  const base = import.meta.env.BASE_URL || '/';
  const response = await fetch(`${base}data/${filename}`);
  if (!response.ok) {
    throw new Error(`Failed to load ${filename}: ${response.status} ${response.statusText}`);
  }
  const text = await response.text();

  return new Promise((resolve, reject) => {
    Papa.parse(text, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        const normalised = normaliseColumns(results.data);
        const typed = normalised.map(typeRow);
        resolve(typed);
      },
      error: (err) => reject(err),
    });
  });
}

/**
 * Convert string values to appropriate types.
 */
function typeRow(row) {
  return {
    ...row,
    UniqueID: parseInt(row.UniqueID, 10) || null,
    SurveyYearMonth: parseInt(row.SurveyYearMonth, 10) || null,
    RenewalYearMonth: parseInt(row.RenewalYearMonth, 10) || null,
    SortOrder: parseInt(row.SortOrder, 10) || null,
    SumRenewal_premium_higher_value: parseFloatOrNull(row.SumRenewal_premium_higher_value),
    SumRenewal_premium_lower_value: parseFloatOrNull(row.SumRenewal_premium_lower_value),
  };
}

function parseFloatOrNull(val) {
  if (val === '' || val === null || val === undefined) return null;
  const num = parseFloat(val);
  return isNaN(num) ? null : num;
}
