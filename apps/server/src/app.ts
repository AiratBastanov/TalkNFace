import { existsSync } from 'node:fs';
import { extname, join } from 'node:path';
import Fastify, { LogController } from 'fastify';
import fastifyStatic from '@fastify/static';
import type Database from 'better-sqlite3';
import type { HealthResponse, ReadinessResponse } from '@arena/contracts';
import type { ServerConfig } from './env.ts';
import { openDatabase } from './database.ts';
import { WEB_ROOT } from './paths.ts';
import { ArenaRepository } from './repositories/arena-repository.ts';
import { SessionService } from './services/session-service.ts';
import { registerG2Routes } from './routes/g2-routes.ts';
import { registerFeedbackRoutes } from './routes/feedback-routes.ts';
import { FeedbackService } from './feedback/service.ts';
import { ContextService } from './context/service.ts';
import { registerContextRoutes } from './routes/context-routes.ts';
import { AccessBoundary } from './access/boundary.ts';

export async function buildApp(config: ServerConfig, options: {
  database?: Database.Database;
  webRoot?: string;
  logger?: boolean;
} = {}) {
  const app = Fastify({ logger: options.logger ? { serializers: {
    req: () => ({ event: 'request' }), res: () => ({ event: 'response' }),
    err: () => ({ type: 'Error', message: 'Request failed', stack: '' }),
  } } : false,
    logController: new LogController({ disableRequestLogging: true }) });
  // The application owns and closes either the supplied or newly opened connection.
  const database = options.database ?? openDatabase(config.DATABASE_PATH);
  app.addHook('onClose', async () => {
    if (database.open) database.close();
    app.log.info({ event: 'database.closed' }, 'SQLite closed');
  });
  app.get<{ Reply: HealthResponse }>('/health', async () => ({ status: 'ok' }));
  app.get<{ Reply: ReadinessResponse }>('/ready', async (_request, reply) => {
    try {
      database.prepare('SELECT COUNT(*) FROM foundation_metadata').get();
      return { status: 'ready' };
    } catch {
      app.log.warn({ event: 'database.not_ready' }, 'SQLite readiness failed');
      return reply.code(503).send({ status: 'not_ready' });
    }
  });

  try {
    const repository = new ArenaRepository(database);
    const access = new AccessBoundary(database, config);
    await access.register(app);
    registerG2Routes(app, new SessionService(repository), access);
    registerFeedbackRoutes(app, new FeedbackService(repository), access);
    registerContextRoutes(app, new ContextService(repository));
    if (config.NODE_ENV === 'production') {
      const webRoot = options.webRoot ?? WEB_ROOT;
      if (!existsSync(join(webRoot, 'index.html'))) {
        throw new Error('Production assets are missing; run npm run build');
      }
      await app.register(fastifyStatic, { root: webRoot });
    }
    app.setNotFoundHandler((request, reply) => {
      let pathname: string;
      try {
        pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      } catch {
        return reply.code(400).send({ status: 'bad_request' });
      }
      const reserved = /^\/(api|health|ready|assets)(\/|$)/i.test(pathname);
      const navigation = (request.method === 'GET' || request.method === 'HEAD')
        && request.headers.accept?.includes('text/html') && !extname(pathname);
      if (config.NODE_ENV === 'production' && navigation && !reserved) {
        return reply.sendFile('index.html');
      }
      return reply.code(404).send({ status: 'not_found' });
    });
    await app.ready();
    return app;
  } catch (error) {
    await app.close();
    throw error;
  }
}
