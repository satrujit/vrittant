/**
 * Sarvam AI integrations: STT WebSocket URL builder + LLM chat proxy.
 * cleanLLMContent strips reasoning tags and markdown artifacts from model
 * output before returning to the UI.
 */

import { apiPost } from '../http.js';
import { API_BASE } from './_internal.js';
import { getAuthToken } from './auth.js';

// Sarvam pro tier caps sarvam-30b at 8192 output tokens — both default and
// retry must stay at the ceiling to avoid 400 invalid_request_error.
const DEFAULT_MAX_TOKENS = 8192;
const MAX_RETRY_TOKENS = 8192;

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
 *   - finish_reason === 'length' (truncation) — doubles max_tokens up to 8192 (Sarvam pro tier cap).
 *   - expectOdia && output is not predominantly Odia — strengthens the system
 *     prompt and retries.
 *   - expectEnglish && output is predominantly Odia — strengthens the system
 *     prompt and retries.
 */
export async function llmChat(arg1, arg2) {
  // Detect legacy positional call: `llmChat(messages, options)`.
  const legacy = Array.isArray(arg1);
  const messages = legacy ? arg1 : arg1?.messages;
  const options = legacy ? (arg2 || {}) : arg1 || {};
  const { max_tokens, temperature, model, expectOdia = false, expectEnglish = false } = options;

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
  const wantOdiaButGotElse = expectOdia && !_isPredominantlyOdia(text);
  const wantEnglishButGotOdia = expectEnglish && _isPredominantlyOdia(text);
  const wrongLang = wantOdiaButGotElse || wantEnglishButGotOdia;

  if (truncated || wrongLang) {
    let retryMessages = messages;
    if (wantOdiaButGotElse) {
      retryMessages = [
        ...(messages || []).filter((m) => m.role !== 'system'),
        {
          role: 'system',
          content:
            'You MUST respond in Odia (ଓଡ଼ିଆ) script only. Do not use English or transliteration.',
        },
      ];
    } else if (wantEnglishButGotOdia) {
      retryMessages = [
        ...(messages || []).filter((m) => m.role !== 'system'),
        {
          role: 'system',
          content:
            'You MUST respond in English only. Do not output any Odia (ଓଡ଼ିଆ) script. Translate every word into natural English.',
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

/**
 * Server-owned story polish via /api/llm/generate-story. Backend picks
 * the model + system prompt (Gemini 2.5 Flash with Sarvam-30b fallback)
 * and applies the same English-script→Odia transliteration, dictation
 * dedup, punctuation cleanup, and digit normalisation the mobile app
 * uses on raw reporter notes. Reusing the same endpoint here keeps the
 * polish behaviour identical between the reporter app and the panel.
 *
 * @param {string} notes — current Odia body (or raw reporter notes)
 * @param {object} [options] — { story_id?: string }
 * @returns {Promise<{body: string, model: string, fallback_used: boolean}>}
 */
export async function generateStory(notes, options = {}) {
  if (!notes || !notes.trim()) return { body: '', model: '', fallback_used: false };
  const payload = { notes };
  if (options.story_id) payload.story_id = options.story_id;
  return await apiPost('/api/llm/generate-story', payload);
}

/**
 * Translate Odia (or another source language) to English via Sarvam's
 * dedicated /translate endpoint. Much more reliable than asking the chat
 * LLM to translate — chat-completions sometimes returns the source
 * language even after a retry. /translate respects target language
 * deterministically (mayura:v1 is a translation model).
 *
 * Backend handles chunking under Sarvam's 1000-char per-request cap.
 *
 * @param {string} text — text to translate
 * @param {object} [options] — { source = 'od-IN', target = 'en-IN', mode = 'formal' }
 * @returns {Promise<string>} translated text
 */
export async function translateText(text, options = {}) {
  if (!text || !text.trim()) return '';
  const {
    source = 'od-IN',
    target = 'en-IN',
    mode = 'formal',
  } = options;
  const res = await apiPost('/api/llm/translate', {
    text,
    source_language_code: source,
    target_language_code: target,
    mode,
  });
  return res?.translated_text ?? '';
}
