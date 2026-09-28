import type { FastifyInstance } from 'fastify';
import { EmptyBodySchema, SessionParamsSchema } from '@arena/contracts/g2';
import { ComparisonQuerySchema, ComparisonSchema, FeedbackQuerySchema, FeedbackReportSchema, PreparationInputSchema, PreparationViewSchema } from '@arena/contracts/feedback';
import type { z } from 'zod';
import { ApiError } from '../api-error.ts';
import type { FeedbackService } from '../feedback/service.ts';
import type { AccessBoundary } from '../access/boundary.ts';

function input<T>(schema: z.ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value);
  if (!result.success) throw new ApiError(400, 'INVALID_REQUEST', 'Некорректная ссылка на попытку или параметры отчёта.');
  return result.data;
}
export function registerFeedbackRoutes(app: FastifyInstance, service: FeedbackService, access: AccessBoundary) {
  app.get('/api/sessions/:sessionId/preparation', async request => {
    input(EmptyBodySchema, request.query);
    return PreparationViewSchema.parse(service.preparation(input(SessionParamsSchema, request.params).sessionId));
  });
  app.post('/api/sessions/:sessionId/preparation', async request => {
    input(EmptyBodySchema, request.query);
    return PreparationViewSchema.parse(service.savePreparation(input(SessionParamsSchema, request.params).sessionId, input(PreparationInputSchema, request.body)));
  });
  app.get('/api/sessions/:sessionId/feedback', async request => {
    const query = input(FeedbackQuerySchema, request.query);
    return FeedbackReportSchema.parse(service.report(input(SessionParamsSchema, request.params).sessionId, query.revision));
  });
  app.get('/api/sessions/:sessionId/feedback/comparison', async request => {
    const query = input(ComparisonQuerySchema, request.query);
    access.assertOwner(request, query.predecessorId);
    return ComparisonSchema.parse(service.comparison(input(SessionParamsSchema, request.params).sessionId, query.revision, query.predecessorId));
  });
}
