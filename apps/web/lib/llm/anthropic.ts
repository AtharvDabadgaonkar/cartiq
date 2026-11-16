/**
 * Anthropic provider. Thin fetch wrapper on purpose: no SDK dependency, so the
 * default (mock) install stays small and the seam stays obvious.
 */
import {
  REFUSAL_SENTINEL,
  extractCitedIds,
  groundingSystemPrompt,
  type CompletionRequest,
  type CompletionResponse,
  type EmbeddingRequest,
  type EmbeddingResponse,
  type LLMProvider,
} from './types';
import { mockEmbed } from './mock';

const API_URL = 'https://api.anthropic.com/v1/messages';
const API_VERSION = '2023-06-01';

interface AnthropicResponse {
  content: { type: string; text?: string }[];
  model: string;
  usage: { input_tokens: number; output_tokens: number };
}

export function createAnthropicProvider(
  apiKey: string,
  model: string,
  embeddingDim: number,
): LLMProvider {
  return {
    name: 'anthropic',
    model,

    async complete(request: CompletionRequest): Promise<CompletionResponse> {
      const started = Date.now();
      const system = [
        groundingSystemPrompt(request.grounding ?? []),
        ...request.messages.filter((m) => m.role === 'system').map((m) => m.content),
      ].join('\n\n');

      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-api-key': apiKey,
          'anthropic-version': API_VERSION,
        },
        body: JSON.stringify({
          model,
          max_tokens: request.maxTokens ?? 1024,
          temperature: request.temperature ?? 0,
          system,
          messages: request.messages
            .filter((m) => m.role !== 'system')
            .map((m) => ({ role: m.role, content: m.content })),
        }),
      });

      if (!response.ok) {
        throw new Error(`anthropic request failed: ${response.status} ${await response.text()}`);
      }

      const body = (await response.json()) as AnthropicResponse;
      const text = body.content
        .filter((block) => block.type === 'text')
        .map((block) => block.text ?? '')
        .join('')
        .trim();

      return {
        text,
        refused: text.includes(REFUSAL_SENTINEL),
        usage: { inputTokens: body.usage.input_tokens, outputTokens: body.usage.output_tokens },
        model: body.model,
        provider: 'anthropic',
        latencyMs: Date.now() - started,
        citedIds: extractCitedIds(text),
      };
    },

    /**
     * Anthropic has no embeddings endpoint. Catalog retrieval therefore uses
     * the deterministic local embedder unless EMBEDDING_PROVIDER=openai.
     */
    async embed(request: EmbeddingRequest): Promise<EmbeddingResponse> {
      return {
        vectors: request.texts.map((t) => mockEmbed(t, embeddingDim)),
        model: 'local-hashed',
        provider: 'local',
        dim: embeddingDim,
      };
    },
  };
}
