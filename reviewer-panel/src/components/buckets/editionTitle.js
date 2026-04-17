/**
 * Build the human-readable display title for an edition in the bucket-detail header.
 * Falls back through: paper-type + formatted date → paper-type + raw date → edition.title → fallback.
 *
 * @param {object|null} edition  Edition object from the API ({paper_type, publication_date, title, ...}).
 * @param {(key: string) => string} t  i18n translator. If a key has no translation it must return the key back.
 * @param {string} fallback  Title to use when `edition` is missing entirely.
 * @returns {string}
 */
export function buildEditionDisplayTitle(edition, t, fallback) {
  if (!edition) return fallback;

  const typeKey = `buckets.paperTypes.${edition.paper_type}`;
  const translated = t(typeKey);
  const typeLabel = translated !== typeKey ? translated : edition.paper_type;

  if (edition.publication_date) {
    const dateStr = edition.publication_date;
    try {
      const d = new Date(dateStr + (dateStr.includes('T') ? '' : 'T00:00:00'));
      const formatted = d.toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      });
      if (Number.isNaN(d.getTime())) {
        return `${typeLabel} - ${dateStr}`;
      }
      return `${typeLabel} - ${formatted}`;
    } catch {
      return `${typeLabel} - ${dateStr}`;
    }
  }

  return edition.title || fallback;
}
