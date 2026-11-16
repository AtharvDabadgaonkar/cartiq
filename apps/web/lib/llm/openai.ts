/** OpenAI provider. Same thin-fetch approach as the Anthropic one. */
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

const CHAT_URL = 'https://api.openai.com/v1/chat/completions';
const EMBED_URL = 'https://api.openai.com/v1/embeddings';

export function createOpenAIProvider(
  apiKey: string,
  model: string,
  embeddingModel: string,
  embeddingDim: number,
): LLMProvider {
  const auth = { authorization: `Bearer ${apiKey}`, 'content-type': 'application/json' };

  return {
    name: 'openai',
    model,

    async complete(request: CompletionRequest): Promise<CompletionResponse> {
      const started = Date.now();
      const response = await fetch(CHAT_URL, {
        method: 'POST',
        headers: auth,
        body: JSON.stringify({
          model,
          temperature: request.temperature ?? 0,
          max_tokens: request.maxTokens ?? 1024,
          ...(request.jsonSchema
            ? {
                response_format: {
                  type: 'json_schema',
                  json_schema: { name: request.jsonSchema.name, schema: request.jsonSchema.schema },
                },
              }
            : {}),
          messages: [
            { role: 'system', content: groundingSystemPrompt(request.grounding ?? []) },
            ...request.messages,
          ],
        }),
      });

      if (!response.ok) {
        throw new Error(`openai request failed: ${response.status} ${await response.text()}`);
      }

      const body = (await response.json()) as {
        model: string;
        choices: { message: { content: string | null } }[];
        usage: { prompt_tokens: number; completion_tokens: number };
      };
      const text = (body.choices[0]?.message.content ?? '').trim();

      return {
        text,
        refused: text.includes(REFUSAL_SENTINEL),
        usage: {
          inputTokens: body.usage.prompt_tokens,
          outputTokens: body.usage.completion_tokens,
        },
        model: body.model,
        provider: 'openai',
        latencyMs: Date.now() - started,
        citedIds: extractCitedIds(text),
      };
    },

    async embed(request: EmbeddingRequest): Promise<EmbeddingResponse> {
      const response = await fetch(EMBED_URL, {
        method: 'POST',
        headers: auth,
        body: JSON.stringify({
          model: embeddingModel,
          input: request.texts,
          dimensions: embeddingDim,
        }),
      });
      if (!response.ok) {
        throw new Error(`openai embeddings failed: ${response.status} ${await response.text()}`);
      }
      const body = (await response.json()) as {
        model: string;
        data: { embedding: number[] }[];
      };
      return {
        vectors: body.data.map((d) => d.embedding),
        model: body.model,
        provider: 'openai',
        dim: embeddingDim,
      };
    },
  };
}

export { REFUSAL_SENTINEL };
