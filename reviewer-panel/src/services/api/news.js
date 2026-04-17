/**
 * News articles ingestion: fetch list, related, search, and the
 * article → researched-story → confirm pipeline.
 */

import { apiFetch, buildQuery } from './_internal.js';

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

export async function searchNewsByTitle(query, limit = 10) {
  return apiFetch(`/admin/news-articles/search-by-title?q=${encodeURIComponent(query)}&limit=${limit}`);
}

export async function confirmResearchedStory(articleId, data) {
  return apiFetch(`/admin/news-articles/${articleId}/confirm-story`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
