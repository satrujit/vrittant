/**
 * Sarvam AI integrations: STT WebSocket URL builder + LLM chat proxy.
 * cleanLLMContent is a private helper that strips reasoning tags and
 * markdown artifacts from model output before returning to the UI.
 */

import { apiPost } from '../http.js';
import { API_BASE } from './_internal.js';
import { getAuthToken } from './auth.js';

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
  const res = await apiPost('/api/llm/chat', {
    messages,
    model: options.model || 'sarvam-30b',
    temperature: options.temperature,
    max_tokens: options.max_tokens || 2048,
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
