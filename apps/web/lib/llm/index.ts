/**
 * Provider factory. Swapping providers is an env change:
 *   LLM_PROVIDER=mock | anthropic | openai
 * `mock` is the default so the app and the full test suite run with no key.
 */
import { serverEnv } from '../env';
import { createAnthropicProvider } from './anthropic';
import { createMockProvider } from './mock';
import { createOpenAIProvider } from './openai';
import { prismaSink } from './prisma-sink';
import { withLogging, type LlmCallSink } from './logging';
import type { LLMProvider } from './types';

export * from './types';
export * from './logging';
export { createMockProvider, mockEmbed } from './mock';

export interface ProviderConfig {
  provider: 'mock' | 'anthropic' | 'openai';
  model: string;
  anthropicApiKey?: string;
  openaiApiKey?: string;
  embeddingModel: string;
  embeddingDim: number;
}

export function createProvider(config: ProviderConfig): LLMProvider {
  switch (config.provider) {
    case 'anthropic':
      if (!config.anthropicApiKey) throw new Error('ANTHROPIC_API_KEY is required');
      return createAnthropicProvider(config.anthropicApiKey, config.model, config.embeddingDim);
    case 'openai':
      if (!config.openaiApiKey) throw new Error('OPENAI_API_KEY is required');
      return createOpenAIProvider(
        config.openaiApiKey,
        config.model,
        config.embeddingModel,
        config.embeddingDim,
      );
    case 'mock':
      return createMockProvider({ dim: config.embeddingDim });
  }
}

let cached: LLMProvider | undefined;

/** The app-wide provider: env-configured and call-logged. */
export function llm(sink?: LlmCallSink): LLMProvider {
  if (cached && !sink) return cached;
  const env = serverEnv();
  const provider = createProvider({
    provider: env.LLM_PROVIDER,
    model: env.LLM_MODEL,
    ...(env.ANTHROPIC_API_KEY ? { anthropicApiKey: env.ANTHROPIC_API_KEY } : {}),
    ...(env.OPENAI_API_KEY ? { openaiApiKey: env.OPENAI_API_KEY } : {}),
    embeddingModel: env.EMBEDDING_MODEL,
    embeddingDim: env.EMBEDDING_DIM,
  });
  const logged = withLogging(provider, sink ?? prismaSink());
  if (!sink) cached = logged;
  return logged;
}
