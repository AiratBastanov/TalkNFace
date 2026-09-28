import { z } from 'zod';
import { ApiErrorSchema as DomainErrorSchema } from './g2.ts';

// Additive application contracts; frozen domain / G2 / interpreter contracts stay unchanged.
export const AccessErrorSchema = DomainErrorSchema.extend({ code: z.enum([
  ...DomainErrorSchema.shape.code.options, 'UNAUTHENTICATED', 'FORBIDDEN', 'CSRF_REJECTED',
  'ORIGIN_REJECTED', 'LOGIN_FAILED', 'LOGIN_THROTTLED', 'ADMIN_UNAVAILABLE',
]) });
export type AccessErrorBody = z.infer<typeof AccessErrorSchema>;
export const AccessSessionSchema = z.strictObject({
  role: z.enum(['player', 'admin']), csrfToken: z.string().regex(/^[A-Za-z0-9_-]{43}$/),
  adminConfigured: z.boolean(), expiresAt: z.int().positive(), idleExpiresAt: z.int().positive(),
});
export type AccessSession = z.infer<typeof AccessSessionSchema>;
