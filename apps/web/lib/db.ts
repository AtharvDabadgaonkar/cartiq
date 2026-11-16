import { PrismaClient } from '@prisma/client';

/**
 * Single Prisma client. Next's dev server re-evaluates modules on every edit,
 * which would otherwise exhaust the connection pool.
 */
const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({ log: process.env.NODE_ENV === 'development' ? ['warn', 'error'] : ['error'] });

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;
