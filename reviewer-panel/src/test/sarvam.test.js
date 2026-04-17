import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../services/http.js', () => ({ apiPost: vi.fn() }));

import { apiPost } from '../services/http.js';
import { llmChat } from '../services/api/sarvam.js';

describe('llmChat', () => {
  beforeEach(() => apiPost.mockReset());

  it('retries with doubled max_tokens on length-truncation', async () => {
    apiPost
      .mockResolvedValueOnce({ choices: [{ message: { content: 'partial' }, finish_reason: 'length' }] })
      .mockResolvedValueOnce({ choices: [{ message: { content: 'complete' }, finish_reason: 'stop' }] });
    const result = await llmChat({ messages: [{ role: 'user', content: 'hi' }] });
    expect(apiPost).toHaveBeenCalledTimes(2);
    expect(apiPost.mock.calls[1][1].max_tokens).toBe(16384);
    expect(result).toBe('complete');
  });

  it('retries with stronger Odia prompt when expectOdia and response is English', async () => {
    apiPost
      .mockResolvedValueOnce({ choices: [{ message: { content: 'English output' }, finish_reason: 'stop' }] })
      .mockResolvedValueOnce({ choices: [{ message: { content: 'ଓଡ଼ିଆ ଅନୁବାଦ' }, finish_reason: 'stop' }] });
    const result = await llmChat({ messages: [{ role: 'user', content: 'translate' }], expectOdia: true });
    expect(apiPost).toHaveBeenCalledTimes(2);
    expect(result).toBe('ଓଡ଼ିଆ ଅନୁବାଦ');
  });

  it('does not retry on success', async () => {
    apiPost.mockResolvedValueOnce({ choices: [{ message: { content: 'fine' }, finish_reason: 'stop' }] });
    await llmChat({ messages: [] });
    expect(apiPost).toHaveBeenCalledTimes(1);
  });
});
