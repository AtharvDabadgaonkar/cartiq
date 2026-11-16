import { prisma } from '../db';
import type { LlmCallSink } from './logging';

/** Persists the LLM call log to Postgres (table `llm_calls`). */
export function prismaSink(): LlmCallSink {
  return {
    async write(record) {
      await prisma.llmCall.create({
        data: {
          purpose: record.purpose,
          provider: record.provider,
          model: record.model,
          prompt: record.prompt,
          grounding: record.grounding,
          response: record.response,
          refused: record.refused,
          citedIds: record.citedIds,
          ungroundedIds: record.ungroundedIds,
          inputTokens: record.inputTokens,
          outputTokens: record.outputTokens,
          latencyMs: record.latencyMs,
          error: record.error ?? null,
          createdAt: record.createdAt,
        },
      });
    },
  };
}
