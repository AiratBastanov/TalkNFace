import type { FastifyInstance } from 'fastify';
import { EmptyBodySchema } from '@arena/contracts/g2';
import { DraftSchema, ContextPublicationSchema } from '@arena/contracts/context-config';
import { ApiError } from '../api-error.ts';
import type { ContextService } from '../context/service.ts';

export function registerContextRoutes(app: FastifyInstance, service: ContextService) {
  const query = (value: unknown) => {
    if (!EmptyBodySchema.safeParse(value).success) throw new ApiError(400, 'INVALID_REQUEST', 'Параметры запроса не поддерживаются.');
  };
  app.get('/api/admin/context-draft', async request => { query(request.query); return DraftSchema.parse(service.get()); });
  app.post('/api/admin/context-draft/save', { bodyLimit: 4096 }, async request => {
    query(request.query); return DraftSchema.parse(service.save(request.body));
  });
  app.post('/api/admin/context-draft/validate', { bodyLimit: 1024 }, async request => {
    query(request.query); return DraftSchema.parse(service.validate(request.body));
  });
  app.post('/api/admin/context-draft/publish', { bodyLimit: 1024 }, async request => {
    query(request.query); return ContextPublicationSchema.parse(service.publish(request.body));
  });
}
