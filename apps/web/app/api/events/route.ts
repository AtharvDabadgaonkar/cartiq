import { NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { parseBatch } from '@/lib/events/ingest';

/** Event ingestion is write-only and must never be cached. */
export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'invalid JSON body' }, { status: 400 });
  }

  const { ok, rows, errors, lagMs } = parseBatch(body);
  if (!ok) {
    // 400 rather than 422: the SDK validates first, so a rejection here is a bug.
    return NextResponse.json({ error: 'invalid event batch', issues: errors }, { status: 400 });
  }

  // Event ids are client-generated UUIDs, so a retried beacon is a no-op.
  const result = await prisma.event.createMany({ data: rows, skipDuplicates: true });

  return NextResponse.json(
    { accepted: result.count, received: rows.length, lagMs },
    { status: 202 },
  );
}
