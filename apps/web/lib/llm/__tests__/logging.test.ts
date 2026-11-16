import { describe, expect, it, vi } from 'vitest';
import { createMockProvider } from '../mock';
import { memorySink, withLogging } from '../logging';
import type { LLMProvider } from '../types';

const grounding = [{ id: 'sku-1', source: 'catalog' as const, text: 'running shoes $89' }];

describe('withLogging', () => {
  it('logs the call together with the exact context supplied', async () => {
    const sink = memorySink();
    const provider = withLogging(createMockProvider({ dim: 32 }), sink);

    await provider.complete({
      purpose: 'shopping_assistant',
      messages: [{ role: 'user', content: 'running shoes' }],
      grounding,
    });

    expect(sink.records).toHaveLength(1);
    const [record] = sink.records;
    expect(record!.purpose).toBe('shopping_assistant');
    expect(record!.grounding).toEqual([
      { id: 'sku-1', source: 'catalog', text: 'running shoes $89' },
    ]);
    expect(record!.prompt).toContain('running shoes');
    expect(record!.citedIds).toContain('sku-1');
  });

  it('flags cited ids that were not in the grounding as ungrounded', async () => {
    const hallucinating: LLMProvider = {
      name: 'fake',
      model: 'fake-1',
      async complete() {
        return {
          text: 'try [sku-999]',
          refused: false,
          usage: { inputTokens: 1, outputTokens: 1 },
          model: 'fake-1',
          provider: 'fake',
          latencyMs: 1,
          citedIds: ['sku-999'],
        };
      },
      async embed() {
        return { vectors: [], model: 'fake-1', provider: 'fake', dim: 0 };
      },
    };

    const sink = memorySink();
    await withLogging(hallucinating, sink).complete({
      purpose: 'shopping_assistant',
      messages: [{ role: 'user', content: 'shoes' }],
      grounding,
    });

    expect(sink.records[0]!.ungroundedIds).toEqual(['sku-999']);
  });

  it('logs failures and rethrows', async () => {
    const failing: LLMProvider = {
      name: 'fake',
      model: 'fake-1',
      complete: vi.fn().mockRejectedValue(new Error('rate limited')),
      async embed() {
        return { vectors: [], model: 'fake-1', provider: 'fake', dim: 0 };
      },
    };
    const sink = memorySink();

    await expect(
      withLogging(failing, sink).complete({
        purpose: 'insights_copilot',
        messages: [{ role: 'user', content: 'why did conversion drop' }],
      }),
    ).rejects.toThrow('rate limited');

    expect(sink.records[0]!.error).toBe('rate limited');
  });

  it('never lets a sink failure break the request', async () => {
    const provider = withLogging(createMockProvider({ dim: 32 }), {
      async write() {
        throw new Error('db down');
      },
    });
    const res = await provider.complete({
      purpose: 'shopping_assistant',
      messages: [{ role: 'user', content: 'running shoes' }],
      grounding,
    });
    expect(res.refused).toBe(false);
  });
});
