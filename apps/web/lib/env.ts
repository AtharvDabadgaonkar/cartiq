import { z } from 'zod';

/**
 * Validated server environment. Importing this from a client component is a
 * build error by design — only `clientEnv` is safe there.
 */
const serverSchema = z.object({
  DATABASE_URL: z.string().min(1),
  DIRECT_URL: z.string().min(1).optional(),
  API_INTERNAL_TOKEN: z.string().min(1).default('dev-only-insecure-token'),
  LLM_PROVIDER: z.enum(['mock', 'anthropic', 'openai']).default('mock'),
  LLM_MODEL: z.string().default('claude-sonnet-4-5'),
  ANTHROPIC_API_KEY: z.string().optional(),
  OPENAI_API_KEY: z.string().optional(),
  EMBEDDING_PROVIDER: z.enum(['mock', 'openai']).default('mock'),
  EMBEDDING_MODEL: z.string().default('text-embedding-3-small'),
  EMBEDDING_DIM: z.coerce.number().int().positive().default(384),
  FLAG_HASH_SALT: z.string().min(1).default('cartiq-v1'),
});

export type ServerEnv = z.infer<typeof serverSchema>;

let cached: ServerEnv | undefined;

export function serverEnv(): ServerEnv {
  if (cached) return cached;
  const parsed = serverSchema.safeParse(process.env);
  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((i) => `  - ${i.path.join('.')}: ${i.message}`)
      .join('\n');
    throw new Error(
      `Invalid server environment:\n${issues}\n\nCopy .env.example to .env (make env).`,
    );
  }
  // A non-mock provider without a key would fail at the first call, far from
  // the cause; fail at boot instead.
  const env = parsed.data;
  if (env.LLM_PROVIDER === 'anthropic' && !env.ANTHROPIC_API_KEY) {
    throw new Error('LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY');
  }
  if (env.LLM_PROVIDER === 'openai' && !env.OPENAI_API_KEY) {
    throw new Error('LLM_PROVIDER=openai requires OPENAI_API_KEY');
  }
  cached = env;
  return env;
}

/** Only NEXT_PUBLIC_* values; safe to read in the browser. */
export const clientEnv = {
  appUrl: process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000',
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
};
