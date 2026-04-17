/**
 * Sarvam AI integrations: STT WebSocket URL builder + LLM chat proxy.
 * cleanLLMContent strips reasoning tags and markdown artifacts from model
 * output before returning to the UI.
 */

import { apiPost } from '../http.js';
import { API_BASE } from './_internal.js';
import { getAuthToken } from './auth.js';

// Long story translations need ≥6k tokens; bump default to avoid truncation.
const DEFAULT_MAX_TOKENS = 8192;
const MAX_RETRY_TOKENS = 16384;

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
    .replace(/^#{1,6}\s+/gm, '')           // headers
    .replace(/\*\*(.+?)\*\*/g, '$1')       // bold
    .replace(/\*(.+?)\*/g, '$1')           // italic
    .replace(/^[-*]\s+/gm, '')             // bullet lists
    .replace(/^\d+\.\s+/gm, '')            // numbered lists
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')  // images
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1') // links
    .trim();
}

/**
 * Heuristic: at least `threshold` of letters are in the Odia Unicode block.
 * Counts Odia-block chars (incl. vowel signs / nukta) as Odia, and counts
 * those + other alphabetic chars as letters.
 */
export function _isPredominantlyOdia(text, threshold = 0.4) {
  if (!text) return false;
  let odia = 0;
  let other = 0;
  for (const c of text) {
    if (c >= '\u0B00' && c <= '\u0B7F') {
      odia += 1;
    } else if (/\p{L}/u.test(c)) {
      other += 1;
    }
  }
  const total = odia + other;
  if (total === 0) return false;
  return odia / total >= threshold;
}

/**
 * Send a chat completion to the backend Sarvam proxy.
 *
 * Two call shapes are supported:
 *   1. New (preferred): `llmChat({ messages, max_tokens?, temperature?, model?, expectOdia? })`
 *      → returns the cleaned text string from the first choice.
 *   2. Legacy: `llmChat(messages, options)` → returns the full response object
 *      (with cleaned content). Kept for backward compatibility.
 *
 * Retries once on:
 *   - finish_reason === 'length' (truncation) — doubles max_tokens up to 16384.
 *   - expectOdia && output is not predominantly Odia — strengthens the system
 *     prompt and retries.
 */
export async function llmChat(arg1, arg2) {
  // Detect legacy positional call: `llmChat(messages, options)`.
  const legacy = Array.isArray(arg1);
  const messages = legacy ? arg1 : arg1?.messages;
  const options = legacy ? (arg2 || {}) : arg1 || {};
  const { max_tokens, temperature, model, expectOdia = false } = options;

  const buildBody = (mt, msgs) => ({
    messages: msgs,
    model: model || 'sarvam-30b',
    temperature,
    max_tokens: mt ?? DEFAULT_MAX_TOKENS,
  });

  let body = buildBody(max_tokens, messages);
  let res = await apiPost('/api/llm/chat', body);
  let text = cleanLLMContent(res?.choices?.[0]?.message?.content ?? '');
  let finishReason = res?.choices?.[0]?.finish_reason;

  const truncated = finishReason === 'length';
  const wrongLang = expectOdia && !_isPredominantlyOdia(text);

  if (truncated || wrongLang) {
    let retryMessages = messages;
    if (wrongLang) {
      retryMessages = [
        ...(messages || []).filter((m) => m.role !== 'system'),
        {
          role: 'system',
          content:
            'You MUST respond in Odia (ଓଡ଼ିଆ) script only. Do not use English or transliteration.',
        },
      ];
    }
    const retryTokens = Math.min((body.max_tokens ?? DEFAULT_MAX_TOKENS) * 2, MAX_RETRY_TOKENS);
    body = buildBody(retryTokens, retryMessages);
    res = await apiPost('/api/llm/chat', body);
    text = cleanLLMContent(res?.choices?.[0]?.message?.content ?? '');
  }

  // Always reflect the (possibly cleaned) content back into the response object
  // so legacy callers reading `res.choices[0].message.content` see clean text.
  if (res?.choices?.[0]?.message) {
    res.choices[0].message.content = text;
  }

  return legacy ? res : text;
}
