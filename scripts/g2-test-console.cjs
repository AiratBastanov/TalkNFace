// Test-only adapter for Windows pipes. It invokes the real production SIGINT
// handler; no HTTP shutdown endpoint or synthetic desktop input is used.
const entry = (process.argv[1] || '').replaceAll('\\', '/');
if (entry.endsWith('/scripts/start.mjs')) {
  console.log(JSON.stringify({ g2Process: true, pid: process.pid, parent: process.ppid }));
  process.stdin.on('data', chunk => {
    if (chunk.toString().trim() === 'g2-stop') {
      process.stdin.pause(); process.stdin.unref?.(); process.emit('SIGINT');
    }
  });
  process.stdin.unref?.();
}
