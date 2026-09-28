import { emitKeypressEvents } from 'node:readline';

export async function readAdminPassword() {
  if (process.argv[2] === '--stdin' && process.argv.length === 3) {
    process.stdin.setEncoding('utf8');
    let value = '';
    for await (const chunk of process.stdin) {
      value += chunk;
      if (value.length > 1024) throw new Error('Password input is too long');
    }
    return value.replace(/\r?\n$/, '');
  }
  if (process.argv.length !== 2 || !process.stdin.isTTY) {
    throw new Error('Use an interactive terminal, or --stdin with a secure prompt; do not put passwords in shell history.');
  }
  process.stderr.write('Administrator password (12-256 characters, hidden): ');
  emitKeypressEvents(process.stdin); process.stdin.setRawMode(true); process.stdin.resume();
  return new Promise((resolve, reject) => {
    let value = '';
    const finish = () => { process.stdin.setRawMode(false); process.stdin.pause(); process.stdin.removeListener('keypress', key); process.stderr.write('\n'); };
    const key = (text, event) => {
      if (event?.ctrl && event.name === 'c') { finish(); reject(new Error('Cancelled')); }
      else if (event?.name === 'return' || event?.name === 'enter') { finish(); resolve(value); }
      else if (event?.name === 'backspace') value = Array.from(value).slice(0, -1).join('');
      else if (text && !event?.ctrl && !/[\u0000-\u001f\u007f]/.test(text) && value.length < 256) value += text;
    };
    process.stdin.on('keypress', key);
  });
}
export function checkPasswordLength(password) {
  if (password.length < 12 || password.length > 256) throw new Error('Use 12-256 characters.');
}
