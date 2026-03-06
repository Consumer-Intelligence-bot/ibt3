/**
 * Shared measure utilities.
 */

/**
 * Filter data to a specific insurer (by CurrentCompany) if provided.
 */
export function filterByInsurer(data, insurer) {
  if (!insurer) return data;
  return data.filter(row => row.CurrentCompany === insurer);
}

/**
 * Exclude new-to-market respondents.
 * Uses the Switchers field which is consistently populated across data shapes.
 */
export function excludeNewToMarket(data) {
  return data.filter(row => row.Switchers !== 'New-to-market');
}
