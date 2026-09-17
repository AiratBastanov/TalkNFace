import { buildApp } from './app.ts';
import { ConfigurationError, parseEnv } from './env.ts';
import type { ServerConfig } from './env.ts';

export async function startServer(config: ServerConfig) {
  const app = await buildApp(config, { logger: true });
  let stopping = false;
  const shutdown = async () => {
    if (stopping) return;
    stopping = true;
    const watchdog = setTimeout(() => {
      console.error('Server shutdown timed out');
      process.exit(1);
    }, 10_000).unref();
    try {
      await app.close();
      process.send?.({ type: 'stopped' });
    } catch {
      console.error('Server shutdown failed');
      process.exitCode = 1;
    } finally {
      clearTimeout(watchdog);
      process.removeListener('SIGINT', onSignal);
      process.removeListener('SIGTERM', onSignal);
      process.removeListener('message', onMessage);
      if (process.connected) process.disconnect();
    }
  };
  const onSignal = () => { void shutdown(); };
  const onMessage = (message: unknown) => {
    // Parent-owned IPC supports clean Windows shutdown; there is no HTTP shutdown route.
    if (message === 'shutdown') void shutdown();
  };
  process.once('SIGINT', onSignal);
  process.once('SIGTERM', onSignal);
  if (process.send) process.on('message', onMessage);
  try {
    await app.listen({ host: config.HOST, port: config.PORT });
    process.send?.({ type: 'started', node: process.version, pid: process.pid });
    return app;
  } catch (error) {
    await shutdown();
    throw error;
  }
}

try {
  await startServer(parseEnv(process.env));
} catch (error) {
  console.error(error instanceof ConfigurationError ? error.message
    : 'Server startup failed: check DATABASE_PATH permissions, HOST/PORT availability and npm run build.');
  process.exitCode = 1;
  if (process.connected) process.disconnect();
}
