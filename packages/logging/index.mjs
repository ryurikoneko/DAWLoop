import fs from 'node:fs/promises';
import path from 'node:path';
import { redact } from '../diagnostics/index.mjs';

export class LogService {
  constructor(root) { this.filename = path.join(root, 'logs', 'desktop.jsonl'); this.entries = []; this.sequence = 0; this.queue = Promise.resolve(); }
  async initialize() {
    await fs.mkdir(path.dirname(this.filename), { recursive: true });
    let handle;
    try {
      handle = await fs.open(this.filename, 'r'); const stat = await handle.stat();
      const start = Math.max(0, stat.size - 256 * 1024); const buffer = Buffer.alloc(stat.size - start);
      await handle.read(buffer, 0, buffer.length, start);
      const lines = buffer.toString('utf8').split('\n'); if (start) lines.shift();
      for (const line of lines) { try { const row = JSON.parse(line); if (Number.isSafeInteger(row.sequence) && typeof row.message === 'string' && ['INFO','WARN','ERROR','DEBUG'].includes(row.level)) this.entries.push(redact(row)); } catch {} }
      this.entries = this.entries.slice(-500); this.sequence = Math.max(0, ...this.entries.map(x => x.sequence));
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
    finally { await handle?.close(); }
  }
  emit(source, level, message) {
    const job = this.queue.then(() => this.append(source, level, message));
    this.queue = job.catch(() => {}); return job;
  }
  async append(source, level, message) {
    const entry = { sequence: ++this.sequence, timestamp: new Date().toISOString(), source, level, message: redact(message) };
    await fs.appendFile(this.filename, JSON.stringify(entry) + '\n', 'utf8');
    this.entries.push(entry); this.entries = this.entries.slice(-500); return entry;
  }
  recent() { return structuredClone(this.entries); }
}
