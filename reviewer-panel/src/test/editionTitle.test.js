import { describe, it, expect } from 'vitest';
import { buildEditionDisplayTitle } from '../components/buckets/editionTitle';

// Translator mock: returns translation if key matches a known map, otherwise returns the key back
// (mirroring the real i18n behaviour the helper relies on).
function makeT(map = {}) {
  return (key) => (key in map ? map[key] : key);
}

describe('buildEditionDisplayTitle', () => {
  it('returns the fallback when edition is null/undefined', () => {
    expect(buildEditionDisplayTitle(null, makeT(), 'Edition')).toBe('Edition');
    expect(buildEditionDisplayTitle(undefined, makeT(), 'Edition')).toBe('Edition');
  });

  it('uses translated paper-type label and formatted date when available', () => {
    const edition = { paper_type: 'morning', publication_date: '2026-04-17' };
    const t = makeT({ 'buckets.paperTypes.morning': 'Morning' });
    expect(buildEditionDisplayTitle(edition, t, 'Edition')).toBe('Morning - 17 Apr 2026');
  });

  it('falls back to raw paper_type when the translation key is missing', () => {
    const edition = { paper_type: 'evening', publication_date: '2026-04-17' };
    expect(buildEditionDisplayTitle(edition, makeT(), 'Edition')).toBe('evening - 17 Apr 2026');
  });

  it('falls back to raw date string when publication_date is unparseable', () => {
    const edition = { paper_type: 'morning', publication_date: 'not-a-date' };
    const t = makeT({ 'buckets.paperTypes.morning': 'Morning' });
    expect(buildEditionDisplayTitle(edition, t, 'Edition')).toBe('Morning - not-a-date');
  });

  it('returns edition.title when there is no publication_date', () => {
    const edition = { paper_type: 'morning', title: 'Custom Title' };
    expect(buildEditionDisplayTitle(edition, makeT(), 'Fallback')).toBe('Custom Title');
  });

  it('returns the fallback when there is neither publication_date nor title', () => {
    const edition = { paper_type: 'morning' };
    expect(buildEditionDisplayTitle(edition, makeT(), 'Fallback')).toBe('Fallback');
  });
});
