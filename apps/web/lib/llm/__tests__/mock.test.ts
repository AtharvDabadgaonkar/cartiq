import { describe, expect, it } from 'vitest';
import { createMockProvider, mockEmbed } from '../mock';
import { REFUSAL_SENTINEL, extractCitedIds, groundingSystemPrompt } from '../types';

const provider = createMockProvider({ dim: 64 });

const catalog = [
  {
    id: 'sku-1',
    source: 'catalog' as const,
    text: 'Trail running shoes, wide fit, $89.00, brand Ridgeline',
  },
  {
    id: 'sku-2',
    source: 'catalog' as const,
    text: 'Road running shoes, neutral arch, $120.00, brand Pacer',
  },
  {
    id: 'sku-3',
    source: 'catalog' as const,
    text: 'Cast iron skillet 12 inch, $45.00, brand Hearth',
  },
];

describe('mock provider grounding behaviour', () => {
  it('refuses when given no context', async () => {
    const res = await provider.complete({
      purpose: 'shopping_assistant',
      messages: [{ role: 'user', content: 'running shoes under $100' }],
    });
    expect(res.refused).toBe(true);
    expect(res.text).toBe(REFUSAL_SENTINEL);
    expect(res.citedIds).toEqual([]);
  });

  it('refuses when nothing in context relates to the question', async () => {
    const res = await provider.complete({
      purpose: 'shopping_assistant',
      messages: [{ role: 'user', content: 'mountain bicycle helmet' }],
      grounding: [catalog[2]!],
    });
    expect(res.refused).toBe(true);
  });

  it('only ever cites ids that were supplied', async () => {
    const res = await provider.complete({
      purpose: 'shopping_assistant',
      messages: [{ role: 'user', content: 'running shoes wide fit' }],
      grounding: catalog,
    });
    expect(res.refused).toBe(false);
    const supplied = new Set(catalog.map((c) => c.id));
    for (const id of res.citedIds) expect(supplied.has(id)).toBe(true);
    expect(res.citedIds).toContain('sku-1');
  });

  it('is deterministic for the same input', async () => {
    const call = () =>
      provider.complete({
        purpose: 'shopping_assistant',
        messages: [{ role: 'user', content: 'road running shoes' }],
        grounding: catalog,
      });
    const [a, b] = await Promise.all([call(), call()]);
    expect(a.text).toBe(b.text);
    expect(a.latencyMs).toBe(b.latencyMs);
  });

  it('returns parseable JSON when a schema is requested', async () => {
    const res = await provider.complete({
      purpose: 'experiment_readout',
      messages: [{ role: 'user', content: 'summarise the conversion lift result' }],
      grounding: [
        {
          id: 'stats-1',
          source: 'experiment_stats',
          text: 'conversion lift 8.4% p 0.012 ci 1.9 to 15.1',
        },
      ],
      jsonSchema: { name: 'readout', schema: { type: 'object' } },
    });
    expect(() => JSON.parse(res.text)).not.toThrow();
  });

  it('reports token usage so cost can be tracked offline', async () => {
    const res = await provider.complete({
      purpose: 'shopping_assistant',
      messages: [{ role: 'user', content: 'running shoes' }],
      grounding: catalog,
    });
    expect(res.usage.inputTokens).toBeGreaterThan(0);
    expect(res.usage.outputTokens).toBeGreaterThan(0);
  });
});

describe('mockEmbed', () => {
  it('is deterministic and unit length', () => {
    const a = mockEmbed('trail running shoes', 64);
    const b = mockEmbed('trail running shoes', 64);
    expect(a).toEqual(b);
    const norm = Math.sqrt(a.reduce((s, v) => s + v * v, 0));
    expect(norm).toBeCloseTo(1, 6);
  });

  it('scores lexically related text higher than unrelated text', () => {
    const dot = (x: number[], y: number[]) => x.reduce((s, v, i) => s + v * (y[i] ?? 0), 0);
    const query = mockEmbed('running shoes wide fit', 256);
    const related = mockEmbed('trail running shoes wide fit brand Ridgeline', 256);
    const unrelated = mockEmbed('cast iron skillet 12 inch', 256);
    expect(dot(query, related)).toBeGreaterThan(dot(query, unrelated));
  });

  it('handles empty input without producing NaN', () => {
    expect(mockEmbed('', 16).every((v) => v === 0)).toBe(true);
  });
});

describe('grounding helpers', () => {
  it('builds a prompt that names the refusal sentinel and lists ids', () => {
    const prompt = groundingSystemPrompt(catalog);
    expect(prompt).toContain(REFUSAL_SENTINEL);
    expect(prompt).toContain('[sku-1]');
  });

  it('extracts and de-duplicates citations in first-seen order', () => {
    expect(extractCitedIds('see [sku-2] and [sku-1], again [sku-2]')).toEqual(['sku-2', 'sku-1']);
    expect(extractCitedIds('no citations here')).toEqual([]);
  });
});
