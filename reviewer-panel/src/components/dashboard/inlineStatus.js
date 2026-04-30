// Canonical status cycle for the dashboard's quick-cycle keyboard shortcut (S)
// and the inline pill dropdown. Ordered by reviewer workflow.
export const STATUS_ORDER = [
  'submitted',
  'in_progress',
  'approved',
  'rejected',
  'flagged',
  'published',
];

export function cycleStatus(current) {
  const i = STATUS_ORDER.indexOf(current);
  if (i === -1) return 'submitted';
  return STATUS_ORDER[(i + 1) % STATUS_ORDER.length];
}

// Soft tinted bg + saturated text — Linear-with-colour palette.
// Tailwind class fragments are kept in the consumer so JIT can pick them up;
// here we only return the semantic accent name for switch-mapping.
export function statusToken(status) {
  switch (status) {
    case 'submitted':   return { accent: 'indigo' };
    case 'in_progress': return { accent: 'sky' };
    case 'approved':    return { accent: 'emerald' };
    case 'rejected':    return { accent: 'rose' };
    case 'flagged':     return { accent: 'amber' };
    case 'published':   return { accent: 'violet' };
    default:            return { accent: 'slate' };
  }
}
