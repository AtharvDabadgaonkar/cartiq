import { NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { serverEnv } from '@/lib/env';

export const dynamic = 'force-dynamic';

/** Liveness + wiring check. Used by `make dev` smoke checks and the e2e suite. */
export async function GET() {
  const env = serverEnv();
  let database: 'up' | 'down' = 'down';
  let eventCount: number | null = null;

  try {
    eventCount = await prisma.event.count();
    database = 'up';
  } catch {
    // Reported as down rather than thrown: the page should still render.
  }

  return NextResponse.json({
    status: database === 'up' ? 'ok' : 'degraded',
    database,
    eventCount,
    llmProvider: env.LLM_PROVIDER,
    embeddingProvider: env.EMBEDDING_PROVIDER,
    phase: 1,
  });
}
