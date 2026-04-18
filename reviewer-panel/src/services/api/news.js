/**
 * News articles ingestion: fetch list, related, search, and the
 * article → researched-story → confirm pipeline.
 */

import { apiGet, apiPost } from '../http.js';
import { buildQuery } from './_internal.js';

// ── News Articles API ──

export async function fetchNewsArticles(params = {}) {
  const query = buildQuery(params);
  return apiGet(`/admin/news-articles${query}`);
}

export async function fetchRelatedArticles(articleId) {
  return apiGet(`/admin/news-articles/${articleId}/related`);
}

export async function researchStoryFromArticle(articleId, { instructions, wordCount, sourceArticleIds, additionalArticleIds } = {}) {
  const body = {};
  if (instructions) body.instructions = instructions;
  if (wordCount) body.word_count = wordCount;
  // Prefer the explicit source list (lets the user pick any subset, including
  // deselecting the route's primary article). Fall back to the legacy
  // additional-only field when callers haven't migrated.
  if (sourceArticleIds?.length) {
    body.source_article_ids = sourceArticleIds;
  } else if (additionalArticleIds?.length) {
    body.additional_article_ids = additionalArticleIds;
  }
  return apiPost(`/admin/news-articles/${articleId}/research-story`, body);
}

export async function searchNewsByTitle(query, limit = 10) {
  return apiGet(`/admin/news-articles/search-by-title?q=${encodeURIComponent(query)}&limit=${limit}`);
}

export async function confirmResearchedStory(articleId, data) {
  return apiPost(`/admin/news-articles/${articleId}/confirm-story`, data);
}
