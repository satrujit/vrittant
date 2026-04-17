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

export async function researchStoryFromArticle(articleId, { instructions, wordCount, additionalArticleIds } = {}) {
  const body = {};
  if (instructions) body.instructions = instructions;
  if (wordCount) body.word_count = wordCount;
  if (additionalArticleIds?.length) body.additional_article_ids = additionalArticleIds;
  return apiPost(`/admin/news-articles/${articleId}/research-story`, body);
}

export async function searchNewsByTitle(query, limit = 10) {
  return apiGet(`/admin/news-articles/search-by-title?q=${encodeURIComponent(query)}&limit=${limit}`);
}

export async function confirmResearchedStory(articleId, data) {
  return apiPost(`/admin/news-articles/${articleId}/confirm-story`, data);
}
