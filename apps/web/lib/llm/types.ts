/**
 * LLM provider interface.
 *
 * Everything the product does with an LLM goes through this seam, so the
 * provider is a config change and the whole app plus the test suite runs with
 * no API key at all (LLM_PROVIDER=mock, the default).
 */

export type Role = 'system' | 'user' | 'assistant';

export interface Message {
  role: Role;
  content: string;
}

/**
 * A retrieved chunk the model is allowed to use. Grounding rule: the model may
 * only assert what appears here. Passed through to the call log so every answer
 * can be audited against what it actually saw.
 */
export interface GroundingChunk {
  /** Stable id of the source row, e.g. a product id. */
  id: string;
  source: 'catalog' | 'metric' | 'sql_result' | 'experiment_stats';
  text: string;
  /** Retrieval score, where the retriever provides one. */
  score?: number;
}

export interface CompletionRequest {
  messages: Message[];
  /** Named for the log, so calls can be grouped by feature. */
  purpose:
    | 'shopping_assistant'
    | 'insights_copilot'
    | 'experiment_readout'
    | 'catalog_fix_suggestion'
    | 'cluster_description';
  grounding?: GroundingChunk[];
  maxTokens?: number;
  temperature?: number;
  /** When set, the provider must return JSON matching this named schema. */
  jsonSchema?: { name: string; schema: Record<string, unknown> };
}

export interface CompletionUsage {
  inputTokens: number;
  outputTokens: number;
}

export interface CompletionResponse {
  text: string;
  /** True when the model declined because the grounding did not support an answer. */
  refused: boolean;
  usage: CompletionUsage;
  model: string;
  provider: string;
  latencyMs: number;
  /** Ids the answer cited, for the hallucination check in Module 4. */
  citedIds: string[];
}

export interface EmbeddingRequest {
  texts: string[];
}

export interface EmbeddingResponse {
  vectors: number[][];
  model: string;
  provider: string;
  dim: number;
}

export interface LLMProvider {
  readonly name: string;
  readonly model: string;
  complete(request: CompletionRequest): Promise<CompletionResponse>;
  embed(request: EmbeddingRequest): Promise<EmbeddingResponse>;
}

/** Sentinel the grounded prompts instruct every provider to emit verbatim. */
export const REFUSAL_SENTINEL = 'INSUFFICIENT_CONTEXT';

/** Standard preamble shared by every grounded feature. */
export function groundingSystemPrompt(grounding: GroundingChunk[]): string {
  const context = grounding.map((c) => `[${c.id}] (${c.source}) ${c.text}`).join('\n');
  return [
    'You are CartIQ, an assistant for an e-commerce storefront and its product team.',
    'You may only state facts that appear in the CONTEXT block below.',
    'Cite the id of every item you reference, in square brackets, e.g. [sku-123].',
    `If the context does not support an answer, reply with exactly ${REFUSAL_SENTINEL} and nothing else.`,
    'Never invent product ids, prices, attributes or metric values.',
    '',
    'CONTEXT:',
    context || '(empty)',
  ].join('\n');
}

/** Extracts `[id]` citations, preserving first-seen order and de-duplicating. */
export function extractCitedIds(text: string): string[] {
  const seen = new Set<string>();
  for (const match of text.matchAll(/\[([A-Za-z0-9_.:-]{1,64})\]/g)) {
    const id = match[1];
    if (id) seen.add(id);
  }
  return [...seen];
}
