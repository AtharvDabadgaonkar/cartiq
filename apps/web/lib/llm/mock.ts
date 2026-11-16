/**
 * Mock LLM provider — the default, so `make dev` and the whole test suite run
 * with no API key.
 *
 * It is not a stub that returns a fixed string. It is deterministic and
 * *grounding-faithful*: it only ever echoes ids and figures that appear in the
 * context, and it refuses when the context is empty. That keeps the grounding
 * and hallucination tests meaningful in CI, where no real provider is reachable.
 */
import {
  REFUSAL_SENTINEL,
  extractCitedIds,
  type CompletionRequest,
  type CompletionResponse,
  type EmbeddingRequest,
  type EmbeddingResponse,
  type LLMProvider,
} from './types';

/** FNV-1a 32-bit; same function the experiment assignment uses. */
function hash32(input: string): number {
  let h = 0x811c9dc5;
  for (const byte of new TextEncoder().encode(input)) {
    h ^= byte;
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

function tokenise(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s$.-]/g, ' ')
    .split(/\s+/)
    .filter((t) => t.length > 1);
}

/**
 * Deterministic hashed bag-of-words embedding ("hashing trick"), L2-normalised.
 * Lexical overlap therefore produces real cosine similarity, so retrieval
 * behaves plausibly offline instead of returning noise.
 */
export function mockEmbed(text: string, dim: number): number[] {
  const vector = new Array<number>(dim).fill(0);
  const tokens = tokenise(text);
  for (const token of tokens) {
    const h = hash32(token);
    const index = h % dim;
    // Signed to reduce collision bias.
    const sign = (h >>> 31) % 2 === 0 ? 1 : -1;
    vector[index] = (vector[index] ?? 0) + sign;
  }
  const norm = Math.sqrt(vector.reduce((sum, v) => sum + v * v, 0));
  if (norm === 0) return vector;
  return vector.map((v) => v / norm);
}

const WORDS_PER_TOKEN = 0.75;

function estimateTokens(text: string): number {
  return Math.max(1, Math.round(text.split(/\s+/).filter(Boolean).length / WORDS_PER_TOKEN));
}

export interface MockProviderOptions {
  dim?: number;
  model?: string;
  /** Simulated latency, in ms, reported but not actually slept. */
  latencyMs?: number;
}

export function createMockProvider(options: MockProviderOptions = {}): LLMProvider {
  const dim = options.dim ?? 384;
  const model = options.model ?? 'mock-deterministic-v1';

  return {
    name: 'mock',
    model,

    async complete(request: CompletionRequest): Promise<CompletionResponse> {
      const grounding = request.grounding ?? [];
      const question =
        [...request.messages].reverse().find((m) => m.role === 'user')?.content ?? '';
      const latencyMs = options.latencyMs ?? 40 + (hash32(question) % 60);
      const base = {
        usage: { inputTokens: 0, outputTokens: 0 },
        model,
        provider: 'mock',
        latencyMs,
      };

      // No context => refuse. This is the behaviour the grounding tests assert.
      if (grounding.length === 0) {
        return {
          ...base,
          text: REFUSAL_SENTINEL,
          refused: true,
          citedIds: [],
          usage: { inputTokens: estimateTokens(question), outputTokens: 1 },
        };
      }

      // Rank context by lexical overlap with the question so the mock's
      // choices respond to the query rather than being positional.
      const queryTokens = new Set(tokenise(question));
      const ranked = [...grounding]
        .map((chunk) => {
          const overlap = tokenise(chunk.text).filter((t) => queryTokens.has(t)).length;
          return { chunk, overlap, score: chunk.score ?? 0 };
        })
        .sort((a, b) => b.overlap - a.overlap || b.score - a.score);

      const picked = ranked.slice(0, Math.min(3, ranked.length));

      // If nothing in context relates to the question at all, refuse rather
      // than answer from parametric memory.
      if (picked.every((p) => p.overlap === 0) && queryTokens.size > 0) {
        return {
          ...base,
          text: REFUSAL_SENTINEL,
          refused: true,
          citedIds: [],
          usage: { inputTokens: estimateTokens(question), outputTokens: 1 },
        };
      }

      const text =
        request.jsonSchema !== undefined
          ? JSON.stringify({
              summary: `Grounded in ${grounding.length} context item(s).`,
              cited_ids: picked.map((p) => p.chunk.id),
              recommendation: 'iterate',
              reasoning:
                'Mock provider: deterministic response derived only from supplied context.',
            })
          : [
              `Based on the catalog and metrics provided, here is what matches: ${picked
                .map((p) => `[${p.chunk.id}]`)
                .join(', ')}.`,
              ...picked.map((p) => `- [${p.chunk.id}] ${p.chunk.text}`),
            ].join('\n');

      return {
        ...base,
        text,
        refused: false,
        citedIds: extractCitedIds(text),
        usage: {
          inputTokens: estimateTokens(question + grounding.map((g) => g.text).join(' ')),
          outputTokens: estimateTokens(text),
        },
      };
    },

    async embed(request: EmbeddingRequest): Promise<EmbeddingResponse> {
      return {
        vectors: request.texts.map((t) => mockEmbed(t, dim)),
        model: `${model}-embed`,
        provider: 'mock',
        dim,
      };
    },
  };
}
