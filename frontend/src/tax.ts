/**
 * Tax label helper — keeps PDF, email and mobile UI in sync.
 * Dominican Republic = ITBIS (the local VAT)
 * Everywhere else    = Tax
 */
export function taxLabel(country?: string | null): string {
  if (!country) return 'Tax';
  const c = String(country).trim().toLowerCase();
  if (
    c.includes('dominican') ||
    c === 'do' ||
    c === 'dom' ||
    c === 'rd' ||
    c === 'dr'
  ) {
    return 'ITBIS';
  }
  return 'Tax';
}
