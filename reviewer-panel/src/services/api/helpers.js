/**
 * Pure UI helpers — colour/initials/media-URL derivation and
 * story/reporter shape transforms. No network calls live here.
 */

import { API_BASE, AVATAR_COLORS } from './_internal.js';
import { normalizeOdiaText } from '../../utils/odiaText.js';

export function getAvatarColor(name) {
  if (!name) return AVATAR_COLORS[0];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

/**
 * Helper: extract initials from a name string.
 */
export function getInitialsFromName(name) {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/**
 * Helper: build the full media URL from a relative path.
 */
export function getMediaUrl(mediaPath) {
  if (!mediaPath) return null;
  if (mediaPath.startsWith('http')) return mediaPath;
  return `${API_BASE}${mediaPath}`;
}

/**
 * Helper: transform an API story object to the shape the UI components expect.
 * - Builds bodyText from paragraphs[].text
 * - Builds reporter.initials and reporter.color from reporter.name
 * - Maps submitted_at to submittedAt (camelCase)
 * - Builds mediaFiles from paragraphs with media_path
 */
export function transformStory(story) {
  if (!story) return null;

  // Parse paragraphs — may be a JSON string or already an array
  let paragraphs = story.paragraphs || [];
  if (typeof paragraphs === 'string') {
    try {
      paragraphs = JSON.parse(paragraphs);
    } catch {
      paragraphs = [];
    }
  }

  // Backfill missing paragraph ids on read. Older stories (and a stretch
  // of reviewer image uploads) didn't include `id`, which broke the
  // attachment-delete UI because we identify paragraphs by id. The synthetic
  // id sticks the moment the story is next saved.
  //
  // Also normalize legacy/reserved Odia codepoints in text (mostly U+0B64
  // → ।) so stored content from WhatsApp forwards and old editors stops
  // rendering as tofu boxes. See utils/odiaText.js.
  paragraphs = paragraphs.map(_normalizeParagraph);

  // Build bodyText from paragraph texts
  const bodyText = paragraphs
    .map((p) => p.text || '')
    .filter(Boolean)
    .join('\n\n');

  // Build reporter info with initials and color
  const reporter = story.reporter || {};
  const reporterName = reporter.name || '';
  const reporterWithUI = {
    ...reporter,
    initials: getInitialsFromName(reporterName),
    color: getAvatarColor(reporterName),
  };

  // Build media files from paragraphs that have media_path. Carry the
  // paragraph id so the UI can delete by id (paragraphs reorder when other
  // paragraphs are removed, so positional indices aren't safe).
  const mediaFiles = paragraphs
    .filter((p) => p.media_path || p.photo_path)
    .map((p) => ({
      paragraphId: p.id,
      type: p.media_type || 'photo',
      url: getMediaUrl(p.media_path || p.photo_path),
      name: p.media_name || 'media',
    }));

  return {
    ...story,
    headline: normalizeOdiaText(story.headline || ''),
    paragraphs,
    bodyText,
    // Human-readable display id (e.g. "PNS-26-1234"). Server populates
    // it from the org code + year + per-org seq_no; falls back to null
    // for legacy stories that pre-date the migration.
    displayId: story.display_id || story.displayId || null,
    seqNo: story.seq_no ?? story.seqNo ?? null,
    reporter: reporterWithUI,
    reporterId: reporter.id || story.reporter_id,
    submittedAt: story.submitted_at || story.submittedAt,
    createdAt: story.created_at || story.createdAt,
    updatedAt: story.updated_at || story.updatedAt,
    location: story.location || reporter.area_name || '',
    mediaFiles,
    // Fallback fields the UI expects
    priority: story.priority || 'normal',
    wordCount: bodyText ? bodyText.trim().split(/\s+/).length : 0,
    aiAccuracy: story.ai_accuracy || story.aiAccuracy || '0',
    // Revision data (editor's version). Normalize the SAME way as the
    // top-level fields — useReviewState prefers revision.paragraphs when
    // a revision exists, so leaving them raw lets U+0B64 leak straight
    // into the editor as tofu boxes.
    revision: _normalizeRevision(story.revision),
    hasRevision: story.has_revision ?? story.revision != null,
  };
}

// Normalize a single paragraph dict: clean Odia codepoints and backfill
// a synthetic id so the attachment-delete UI can identify it.
function _normalizeParagraph(p) {
  if (!p || typeof p !== 'object') return p;
  const next = { ...p };
  if (typeof next.text === 'string') {
    next.text = normalizeOdiaText(next.text);
  }
  if (!next.id) {
    next.id = (typeof crypto !== 'undefined' && crypto.randomUUID)
      ? crypto.randomUUID()
      : `p-${Math.random().toString(36).slice(2, 10)}-${Date.now().toString(36)}`;
  }
  return next;
}

// Normalize the revision payload. Mirror the top-level cleanup so the
// editor never receives raw U+0B64. Also handles the JSON-string vs
// already-parsed case for `paragraphs`, the same way we do above.
function _normalizeRevision(rev) {
  if (!rev || typeof rev !== 'object') return rev || null;
  let revParas = rev.paragraphs || [];
  if (typeof revParas === 'string') {
    try { revParas = JSON.parse(revParas); } catch { revParas = []; }
  }
  return {
    ...rev,
    headline: typeof rev.headline === 'string'
      ? normalizeOdiaText(rev.headline)
      : rev.headline,
    paragraphs: Array.isArray(revParas) ? revParas.map(_normalizeParagraph) : revParas,
    english_translation: typeof rev.english_translation === 'string'
      ? normalizeOdiaText(rev.english_translation)
      : rev.english_translation,
  };
}

/**
 * Helper: transform an API reporter object to the shape the UI components expect.
 */
export function transformReporter(reporter) {
  if (!reporter) return null;
  const name = reporter.name || '';
  return {
    ...reporter,
    initials: getInitialsFromName(name),
    color: getAvatarColor(name),
    areaName: reporter.area_name || reporter.areaName || '',
    organization: reporter.organization || '',
    isActive: reporter.is_active ?? reporter.isActive ?? true,
    submissionCount: reporter.submission_count ?? reporter.submissionCount ?? 0,
    publishedCount: reporter.published_count ?? reporter.publishedCount ?? 0,
    lastActive: reporter.last_active || reporter.lastActive || null,
  };
}
