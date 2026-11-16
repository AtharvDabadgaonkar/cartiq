/**
 * Every LLM call is logged together with the exact context it was given.
 * That log is what makes Module 4's grounding/hallucination evaluation and the
 * assistant-quality guardrail possible after the fact, rather than only live.
 */
import type { CompletionRequest, CompletionResponse, LLMProvider } from './types';

export interface LlmCallRecord {
  purpose: CompletionRequest['purpose'];
  provider: string;
  model: string;
  prompt: string;
  /** Ids + text of every chunk the model was allowed to use. */
  grounding: { id: string; source: string; text: string; score?: number }[];
  response: string;
  refused: boolean;
  citedIds: string[];
  /** Cited ids that were NOT in the supplied grounding: ungrounded by construction. */
  ungroundedIds: string[];
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
  error?: string;
  createdAt: Date;
}

export interface LlmCallSink {
  write(record: LlmCallRecord): Promise<void>;
}

/** In-memory sink for tests and for the evaluation harness. */
export function memorySink(): LlmCallSink & { records: LlmCallRecord[] } {
  const records: LlmCallRecord[] = [];
  return {
    records,
    async write(record) {
      records.push(record);
    },
  };
}

/** Never let telemetry break a user-facing request. */
export function safeSink(sink: LlmCallSink): LlmCallSink {
  return {
    async write(record) {
      try {
        await sink.write(record);
      } catch (error) {
        console.error('[cartiq] llm call log write failed', error);
      }
    },
  };
}

export function withLogging(provider: LLMProvider, sink: LlmCallSink): LLMProvider {
  const guarded = safeSink(sink);

  return {
    name: provider.name,
    model: provider.model,
    embed: provider.embed.bind(provider),

    async complete(request: CompletionRequest): Promise<CompletionResponse> {
      const grounding = (request.grounding ?? []).map((c) => ({
        id: c.id,
        source: c.source,
        text: c.text,
        ...(c.score !== undefined ? { score: c.score } : {}),
      }));
      const prompt = request.messages.map((m) => `${m.role}: ${m.content}`).join('\n');
      const groundedIds = new Set(grounding.map((c) => c.id));
      const started = Date.now();

      try {
        const response = await provider.complete(request);
        await guarded.write({
          purpose: request.purpose,
          provider: response.provider,
          model: response.model,
          prompt,
          grounding,
          response: response.text,
          refused: response.refused,
          citedIds: response.citedIds,
          ungroundedIds: response.citedIds.filter((id) => !groundedIds.has(id)),
          inputTokens: response.usage.inputTokens,
          outputTokens: response.usage.outputTokens,
          latencyMs: response.latencyMs,
          createdAt: new Date(),
        });
        return response;
      } catch (error) {
        await guarded.write({
          purpose: request.purpose,
          provider: provider.name,
          model: provider.model,
          prompt,
          grounding,
          response: '',
          refused: false,
          citedIds: [],
          ungroundedIds: [],
          inputTokens: 0,
          outputTokens: 0,
          latencyMs: Date.now() - started,
          error: error instanceof Error ? error.message : String(error),
          createdAt: new Date(),
        });
        throw error;
      }
    },
  };
}
