/**
 * Vrittant Reviewer Panel — API Service Layer
 * Connects to the FastAPI backend at the configured base URL.
 */

const API_BASE = import.meta.env.VITE_API_BASE;

// ── Token management ──

export function getAuthToken() {
  return localStorage.getItem('vr_token');
}
export function setAuthToken(token) {
  localStorage.setItem('vr_token', token);
}
export function clearAuthToken() {
  localStorage.removeItem('vr_token');
}

/**
 * Generic fetch wrapper with error handling.
 * Returns parsed JSON on success, throws on failure.
 */
async function apiFetch(path, options = {}) {
  const token = getAuthToken();
  const url = `${API_BASE}${path}`;
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
      ...options,
    });

    if (response.status === 401) {
      clearAuthToken();
      window.location.href = '/login';
      throw new Error('Session expired');
    }

    if (!response.ok) {
      const errorBody = await response.text().catch(() => '');
      throw new Error(
        `API error ${response.status}: ${response.statusText}${errorBody ? ` — ${errorBody}` : ''}`
      );
    }

    // 204 No Content has no body
    if (response.status === 204) return null;
    return await response.json();
  } catch (err) {
    if (err.message.startsWith('API error') || err.message === 'Session expired') {
      throw err;
    }
    throw new Error(`Network error: ${err.message}`);
  }
}

/**
 * Build a query string from a params object, omitting empty values.
 */
function buildQuery(params) {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== ''
  );
  if (entries.length === 0) return '';
  return '?' + new URLSearchParams(entries).toString();
}

/**
 * GET /admin/stats
 * Returns: { pending_review, reviewed_today, avg_ai_accuracy, total_published, total_stories, total_reporters }
 */
export async function fetchStats() {
  return apiFetch('/admin/stats');
}

export async function fetchActivityHeatmap(days = 365, reporterId = null) {
  let url = `/admin/activity-heatmap?days=${days}`;
  if (reporterId) url += `&reporter_id=${reporterId}`;
  return apiFetch(url);
}

export async function fetchLeaderboard(period = 'month') {
  return apiFetch(`/admin/leaderboard?period=${period}`);
}

export async function semanticSearchStories(params = {}) {
  const searchParams = new URLSearchParams();
  if (params.q) searchParams.set('q', params.q);
  if (params.offset != null) searchParams.set('offset', String(params.offset));
  if (params.limit != null) searchParams.set('limit', String(params.limit));
  return apiFetch(`/admin/stories/semantic-search?${searchParams.toString()}`);
}

/**
 * GET /admin/stories
 * @param {object} params — { status, category, search, date_from, date_to, recent, offset, limit }
 * Returns: { stories: [...], total: N }
 */
export async function fetchStories(params = {}) {
  const query = buildQuery(params);
  return apiFetch(`/admin/stories${query}`);
}

/**
 * GET /admin/stories/:id
 * Returns a single story object with nested reporter info.
 */
export async function fetchStory(id) {
  return apiFetch(`/admin/stories/${id}`);
}

/**
 * PUT /admin/stories/:id/status
 * @param {string|number} id
 * @param {string} status — "approved"|"rejected"|"published"|"in_progress"
 * @param {string} reason — optional reason for rejection or changes
 */
export async function updateStoryStatus(id, status, reason = '') {
  return apiFetch(`/admin/stories/${id}/status`, {
    method: 'PUT',
    body: JSON.stringify({ status, reason }),
  });
}

/**
 * PUT /admin/stories/:id
 * @param {string|number} id
 * @param {object} data — { headline, category, paragraphs }
 */
export async function updateStory(id, data) {
  return apiFetch(`/admin/stories/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * GET /admin/reporters
 * Returns: { reporters: [...] }
 */
export async function fetchReporters({ includeInactive = false } = {}) {
  const params = includeInactive ? '?include_inactive=true' : '';
  return apiFetch(`/admin/reporters${params}`);
}

/**
 * GET /admin/reporters/:id/stories
 * @param {string|number} reporterId
 * @param {object} params — same filters as fetchStories
 * Returns: { stories: [...], total: N }
 */
export async function fetchReporterStories(reporterId, params = {}) {
  const query = buildQuery(params);
  return apiFetch(`/admin/reporters/${reporterId}/stories${query}`);
}

/**
 * Helper: generates avatar color from a reporter name.
 * Uses a simple string hash to pick from a predefined color palette.
 */
const AVATAR_COLORS = [
  '#FA6C38', '#3D3B8E', '#14B8A6', '#6366F1',
  '#EC4899', '#F59E0B', '#10B981', '#EF4444',
  '#8B5CF6', '#0EA5E9', '#D97706', '#059669',
  '#E11D48', '#7C3AED', '#0891B2', '#CA8A04',
];

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

  // Build media files from paragraphs that have media_path
  const mediaFiles = paragraphs
    .filter((p) => p.media_path || p.photo_path)
    .map((p) => ({
      type: p.media_type || 'photo',
      url: getMediaUrl(p.media_path || p.photo_path),
      name: p.media_name || 'media',
    }));

  return {
    ...story,
    paragraphs,
    bodyText,
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
    // Revision data (editor's version)
    revision: story.revision || null,
    hasRevision: story.has_revision ?? story.revision != null,
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

// ── Templates API ──

export async function fetchTemplates() {
  return apiFetch('/admin/templates');
}

export async function fetchTemplate(id) {
  return apiFetch(`/admin/templates/${id}`);
}

export async function createTemplate(data) {
  return apiFetch('/admin/templates', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateTemplate(id, data) {
  return apiFetch(`/admin/templates/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteTemplate(id) {
  return apiFetch(`/admin/templates/${id}`, { method: 'DELETE' });
}

// ── Layout Templates API ──

export async function fetchLayoutTemplates(category) {
  const query = category ? `?category=${encodeURIComponent(category)}` : '';
  return apiFetch(`/admin/layout-templates${query}`);
}

export async function fetchLayoutTemplate(id) {
  return apiFetch(`/admin/layout-templates/${id}`);
}

export async function createLayoutTemplate(data) {
  return apiFetch('/admin/layout-templates', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateLayoutTemplate(id, data) {
  return apiFetch(`/admin/layout-templates/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteLayoutTemplate(id) {
  return apiFetch(`/admin/layout-templates/${id}`, { method: 'DELETE' });
}

// ── AI Layout + IDML Export ──

export async function generateAutoLayout(storyId, options = {}) {
  return apiFetch(`/admin/stories/${storyId}/auto-layout`, {
    method: 'POST',
    body: JSON.stringify({
      instructions: options.instructions || null,
      headline: options.headline || null,
      paragraphs: options.paragraphs || null,
      layout_template_id: options.layoutTemplateId || null,
      preferences: options.preferences || null,
    }),
  });
}

export async function exportIdml(storyId) {
  const token = getAuthToken();
  const resp = await fetch(`${API_BASE}/admin/stories/${storyId}/export-idml`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({}),
  });
  if (!resp.ok) throw new Error(`Export failed: ${resp.status}`);
  const blob = await resp.blob();
  const filename = resp.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] || 'layout.idml';
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ── Editions API ──

export async function fetchEditions(params = {}) {
  const query = buildQuery(params);
  return apiFetch(`/admin/editions${query}`);
}

export async function fetchEdition(id) {
  return apiFetch(`/admin/editions/${id}`);
}

export async function createEdition(data) {
  return apiFetch('/admin/editions', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateEdition(id, data) {
  return apiFetch(`/admin/editions/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteEdition(id) {
  return apiFetch(`/admin/editions/${id}`, { method: 'DELETE' });
}

export async function addEditionPage(editionId, data) {
  return apiFetch(`/admin/editions/${editionId}/pages`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateEditionPage(editionId, pageId, data) {
  return apiFetch(`/admin/editions/${editionId}/pages/${pageId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteEditionPage(editionId, pageId) {
  return apiFetch(`/admin/editions/${editionId}/pages/${pageId}`, {
    method: 'DELETE',
  });
}

export async function assignStoriesToPage(editionId, pageId, storyIds) {
  return apiFetch(`/admin/editions/${editionId}/pages/${pageId}/stories`, {
    method: 'PUT',
    body: JSON.stringify({ story_ids: storyIds }),
  });
}

export async function exportEditionZip(editionId) {
  const token = getAuthToken();
  const resp = await fetch(`${API_BASE}/admin/editions/${editionId}/export-zip`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `Export failed: ${resp.status}`);
  }
  const blob = await resp.blob();
  const filename = resp.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] || 'edition.zip';
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ── Org Admin API ──

export async function fetchOrgUsers({ includeInactive = false } = {}) {
  const params = includeInactive ? '?include_inactive=true' : '';
  return apiFetch(`/admin/reporters${params}`);
}

export async function createUser(data) {
  return apiFetch('/admin/users', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateUser(id, data) {
  return apiFetch(`/admin/users/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function updateUserRole(id, userType) {
  return apiFetch(`/admin/users/${id}/role`, {
    method: 'PUT',
    body: JSON.stringify({ user_type: userType }),
  });
}

export async function updateUserEntitlements(id, pageKeys) {
  return apiFetch(`/admin/users/${id}/entitlements`, {
    method: 'PUT',
    body: JSON.stringify({ page_keys: pageKeys }),
  });
}

export async function updateOrg(data) {
  return apiFetch('/admin/org', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function uploadOrgLogo(file) {
  const token = getAuthToken();
  const formData = new FormData();
  formData.append('file', file);
  const resp = await fetch(`${API_BASE}/admin/org/logo`, {
    method: 'PUT',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: formData,
  });
  if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`);
  return resp.json();
}

export async function fetchOrgConfig() {
  return apiFetch('/admin/config');
}

export async function updateOrgConfig(data) {
  return apiFetch('/admin/config', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteStory(id) {
  return apiFetch(`/admin/stories/${id}`, { method: 'DELETE' });
}

// ── Auth API ──

export async function checkPhone(phone) {
  return apiFetch('/auth/check-phone', { method: 'POST', body: JSON.stringify({ phone }) });
}

export async function msg91Login(phone, accessToken) {
  return apiFetch('/auth/msg91-login', {
    method: 'POST',
    body: JSON.stringify({ phone, access_token: accessToken }),
  });
}

export async function firebaseLogin(firebaseToken) {
  return apiFetch('/auth/firebase-login', {
    method: 'POST',
    body: JSON.stringify({ firebase_token: firebaseToken }),
  });
}

export async function fetchCurrentUser() {
  return apiFetch('/auth/me');
}

/**
 * Build the WebSocket URL for the Sarvam STT proxy.
 * @param {string} languageCode — e.g. 'od-IN' for Odia
 * @param {string} model — e.g. 'saaras:v3'
 * @returns {string} WebSocket URL with auth token
 */
export function getSTTWebSocketUrl(languageCode = 'od-IN', model = 'saaras:v3') {
  const token = getAuthToken();
  const wsBase = API_BASE.replace(/^http/, 'ws');
  return `${wsBase}/ws/stt?token=${token}&language_code=${languageCode}&model=${model}`;
}

/** Strip model reasoning tags and markdown artifacts from LLM output */
function cleanLLMContent(text) {
  return text
    // Strip <think>/<thinking> reasoning blocks
    .replace(/<think(?:ing)?>[\s\S]*?<\/think(?:ing)?>/g, '')
    .replace(/<think(?:ing)?>[\s\S]*/g, '')
    // Strip markdown formatting
    .replace(/^#{1,6}\s+/gm, '')           // headers: ## Headline → Headline
    .replace(/\*\*(.+?)\*\*/g, '$1')       // bold: **text** → text
    .replace(/\*(.+?)\*/g, '$1')           // italic: *text* → text
    .replace(/^[-*]\s+/gm, '')             // bullet lists
    .replace(/^\d+\.\s+/gm, '')            // numbered lists
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')  // images
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1') // links: [text](url) → text
    .trim();
}

export async function llmChat(messages, options = {}) {
  const res = await apiFetch('/api/llm/chat', {
    method: 'POST',
    body: JSON.stringify({
      messages,
      model: options.model || 'sarvam-30b',
      temperature: options.temperature,
      max_tokens: options.max_tokens || 2048,
    }),
  });
  // Strip <think>/<thinking> tags from all choices
  if (res?.choices) {
    for (const choice of res.choices) {
      if (choice?.message?.content) {
        choice.message.content = cleanLLMContent(choice.message.content);
      }
    }
  }
  return res;
}

// ── News Articles API ──

export async function fetchNewsArticles(params = {}) {
  const query = buildQuery(params);
  return apiFetch(`/admin/news-articles${query}`);
}

export async function fetchRelatedArticles(articleId) {
  return apiFetch(`/admin/news-articles/${articleId}/related`);
}

export async function researchStoryFromArticle(articleId, { instructions, wordCount, additionalArticleIds } = {}) {
  const body = {};
  if (instructions) body.instructions = instructions;
  if (wordCount) body.word_count = wordCount;
  if (additionalArticleIds?.length) body.additional_article_ids = additionalArticleIds;
  return apiFetch(`/admin/news-articles/${articleId}/research-story`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function fetchRelatedStories(storyId) {
  return apiFetch(`/admin/stories/${storyId}/related`);
}

export async function searchNewsByTitle(query, limit = 10) {
  return apiFetch(`/admin/news-articles/search-by-title?q=${encodeURIComponent(query)}&limit=${limit}`);
}

export async function confirmResearchedStory(articleId, data) {
  return apiFetch(`/admin/news-articles/${articleId}/confirm-story`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function createBlankStory() {
  return apiFetch('/admin/stories/create-blank', {
    method: 'POST',
  });
}

export async function uploadStoryImage(storyId, file) {
  const token = getAuthToken();
  const formData = new FormData();
  formData.append('file', file);
  const resp = await fetch(`${API_BASE}/admin/stories/${storyId}/upload-image`, {
    method: 'POST',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: formData,
  });
  if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`);
  return resp.json();
}
