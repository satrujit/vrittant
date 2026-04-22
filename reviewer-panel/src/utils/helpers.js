/**
 * Vrittant Reviewer Panel — Utility Helpers
 */

import { generateICML as icmlExport } from './icml';

/**
 * Parse a date string as IST (UTC+5:30).
 * The backend stores timestamps in IST via now_ist(), but without timezone
 * info in the ISO string, so the browser wrongly treats them as UTC.
 */
function parseIST(isoDate) {
  const d = new Date(isoDate);
  // If the ISO string has no timezone suffix, it was parsed as UTC.
  // Subtract 5:30 so that when the browser converts to IST for display,
  // the result matches the original IST value stored in the DB.
  if (typeof isoDate === 'string' && !isoDate.match(/[Zz+\-]\d/)) {
    d.setMinutes(d.getMinutes() - 330); // 5h30m = 330 min
  }
  return d;
}

/**
 * Returns a human-readable relative time string from an ISO date.
 * Examples: "Just now", "3 min ago", "5h ago", "Yesterday"
 */
export function formatTimeAgo(isoDate) {
  if (!isoDate) return '';

  const now = new Date();
  const date = parseIST(isoDate);
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'Just now';
  if (diffMin < 60) return `${diffMin} min ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay === 1) return 'Yesterday';
  if (diffDay < 7) return `${diffDay}d ago`;

  return date.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
}

/**
 * Returns a formatted date string like "Today, 10:24 AM" or "Yesterday, 3:15 PM".
 */
export function formatDate(isoDate) {
  if (!isoDate) return '';

  const now = new Date();
  const date = parseIST(isoDate);

  const timeStr = date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });

  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diffDays = Math.floor((today - target) / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return `Today, ${timeStr}`;
  if (diffDays === 1) return `Yesterday, ${timeStr}`;

  const dateStr = date.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
  });
  return `${dateStr}, ${timeStr}`;
}

/**
 * Returns CSS variable-based color and background for a given category.
 */
export function getCategoryColor(category) {
  const key = category?.toLowerCase().replace(/[\s_]+/g, '') || 'politics';

  const map = {
    politics:       { color: '#6366F1', bg: '#EEF2FF' },
    sports:         { color: '#14B8A6', bg: '#CCFBF1' },
    crime:          { color: '#EF4444', bg: '#FEE2E2' },
    business:       { color: '#F59E0B', bg: '#FEF3C7' },
    entertainment:  { color: '#EC4899', bg: '#FCE7F3' },
    education:      { color: '#8B5CF6', bg: '#EDE9FE' },
    health:         { color: '#22C55E', bg: '#DCFCE7' },
    technology:     { color: '#3B82F6', bg: '#DBEAFE' },
    urbanplanning:  { color: '#0EA5E9', bg: '#E0F2FE' },
    urban:          { color: '#0EA5E9', bg: '#E0F2FE' },
    sustainability: { color: '#059669', bg: '#D1FAE5' },
    economics:      { color: '#D97706', bg: '#FEF3C7' },
    lifestyle:      { color: '#F472B6', bg: '#FCE7F3' },
    finance:        { color: '#F59E0B', bg: '#FEF3C7' },
  };

  return map[key] || { color: '#6366F1', bg: '#EEF2FF' };
}

/**
 * Returns CSS variable-based color, background, and dot color for a given status.
 */
export function getStatusColor(status) {
  const key = status?.toLowerCase().replace(/[\s_]+/g, '') || 'draft';

  const map = {
    submitted:    { color: '#F59E0B', bg: '#FEF3C7', dot: '#F59E0B' },
    pending:      { color: '#F59E0B', bg: '#FEF3C7', dot: '#F59E0B' },
    pendingreview:{ color: '#F59E0B', bg: '#FEF3C7', dot: '#F59E0B' },
    inprogress:   { color: '#3B82F6', bg: '#DBEAFE', dot: '#3B82F6' },
    in_progress:  { color: '#3B82F6', bg: '#DBEAFE', dot: '#3B82F6' },
    approved:     { color: '#10B981', bg: '#D1FAE5', dot: '#10B981' },
    rejected:     { color: '#EF4444', bg: '#FEE2E2', dot: '#EF4444' },
    flagged:      { color: '#F59E0B', bg: '#FEF3C7', dot: '#F59E0B' },
    published:    { color: '#10B981', bg: '#D1FAE5', dot: '#10B981' },
    draft:        { color: '#A8A29E', bg: '#F5F5F4', dot: '#A8A29E' },
  };

  return map[key] || { color: '#A8A29E', bg: '#F5F5F4', dot: '#A8A29E' };
}

/**
 * Returns the first two uppercase initials from a name string.
 */
export function getInitials(name) {
  if (!name) return '';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/**
 * Truncates text to a maximum length and appends an ellipsis if truncated.
 */
export function truncateText(text, maxLen = 100) {
  if (!text) return '';
  if (text.length <= maxLen) return text;
  return text.substring(0, maxLen).trimEnd() + '...';
}

/**
 * Generates an InDesign ICML XML string from a story object.
 * Delegates to the dedicated icml.js module.
 */
export function generateICML(story) {
  return icmlExport(story);
}

/**
 * Generates a platform-optimized social media post from a story object.
 * @param {object} story — must have headline, bodyText, category, reporter
 * @param {'twitter'|'facebook'|'instagram'} platform
 * @returns {string}
 */
export function generateSocialPost(story, platform) {
  if (!story) return '';

  const { headline = '', bodyText = '', category = '', reporter } = story;
  const reporterName = reporter?.name || '';
  const categoryTag = `#${category.replace(/[\s_]+/g, '')}`;
  const locationTag = story.location ? `#${story.location.replace(/\s+/g, '')}` : '';

  switch (platform) {
    case 'twitter': {
      const tags = `${categoryTag} #Vrittant`;
      const maxBody = 280 - headline.length - tags.length - 6; // 6 for newlines + separators
      const body = maxBody > 20 ? truncateText(bodyText, maxBody) : '';
      let tweet = headline;
      if (body) tweet += `\n\n${body}`;
      tweet += `\n\n${tags}`;
      return tweet.substring(0, 280);
    }

    case 'facebook': {
      let post = headline;
      post += `\n\n${truncateText(bodyText, 500)}`;
      if (reporterName) post += `\n\nReported by ${reporterName}`;
      if (story.location) post += ` from ${story.location}`;
      post += `\n\n${categoryTag} ${locationTag} #Vrittant #News`.trim();
      return post;
    }

    case 'instagram': {
      let caption = headline;
      caption += `\n\n${truncateText(bodyText, 400)}`;
      if (reporterName) caption += `\n\nBy ${reporterName}`;
      caption += '\n\n---\n';
      const hashtags = [
        categoryTag,
        locationTag,
        '#Vrittant',
        '#News',
        '#BreakingNews',
        '#Odisha',
        '#Journalism',
      ].filter(Boolean).join(' ');
      caption += hashtags;
      return caption;
    }

    default:
      return headline;
  }
}
