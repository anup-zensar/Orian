/** Fluent badge colour for a support model status. */
export function statusColor(status: string): 'informative' | 'warning' | 'success' | 'subtle' {
  if (status === 'Agreed') return 'success';
  if (status === 'In review') return 'warning';
  if (status === 'Draft') return 'informative';
  return 'subtle';
}
