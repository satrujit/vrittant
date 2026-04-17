/**
 * Story templates, layout templates, AI auto-layout, and IDML export.
 */

import { API_BASE, apiFetch } from './_internal.js';
import { getAuthToken } from './auth.js';

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
