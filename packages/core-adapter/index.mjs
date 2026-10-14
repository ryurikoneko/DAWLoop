import { spawn } from 'node:child_process';
import { AppError } from '../config/index.mjs';
import { redact } from '../diagnostics/index.mjs';

export const mockScenarios = ['connected', 'disconnected', 'degraded', 'faulted', 'offline', 'timeout', 'backend-error'];
export const unavailable = () => ({ runtime: { state: 'unknown', version: null, controllable: false, reason: 'CORE_OBSERVER_UNAVAILABLE' },
  host: { state: 'unknown', detected: null, processRunning: null, version: null, reason: 'NOT_OBSERVED' },
  bridges: ['controller','gopher','mcp','sysex'].map(id => ({ id, state: 'unknown', reason: 'NOT_OBSERVED' })), capabilities: [] });
export function validateSnapshot(value) {
  const connections = ['unknown','checking','connected','disconnected','degraded','error'];
  const code = x => typeof x === 'string' && /^[A-Z0-9_]{1,120}$/.test(x);
  const version = x => x === null || (typeof x === 'string' && /^[a-zA-Z0-9.+_-]{1,80}$/.test(x));
  if (value?.apiVersion !== 1 || !['unknown','stopped','starting','running','stopping','faulted'].includes(value.runtime?.state)
    || typeof value.runtime?.controllable !== 'boolean' || !code(value.runtime?.reason) || !version(value.runtime?.version) || !connections.includes(value.host?.state)
    || !code(value.host?.reason) || !version(value.host?.version)
    || ![true,false,null].includes(value.host?.detected) || ![true,false,null].includes(value.host?.processRunning)
    || !Array.isArray(value.bridges) || value.bridges.length > 32 || !value.bridges.every(x => typeof x.id === 'string' && /^[a-z0-9.-]{1,80}$/.test(x.id) && connections.includes(x.state) && code(x.reason))
    || !Array.isArray(value.capabilities) || value.capabilities.length > 128 || !value.capabilities.every(x => typeof x.id === 'string' && /^[a-z0-9.-]{1,100}$/.test(x.id) && ['available','partial','experimental','unavailable','unknown'].includes(x.state)
      && ['high','medium','low','very-low','unknown'].includes(x.confidence) && typeof x.backend === 'string' && /^[a-z0-9.-]{1,80}$/.test(x.backend) && Array.isArray(x.notes) && x.notes.length <= 16 && x.notes.every(note=>typeof note === 'string' && note.length <= 500)))
    throw new AppError('INVALID_BACKEND_RESPONSE', 'backend');
  return { apiVersion:1,
    runtime: { state:value.runtime.state, version:value.runtime.version, controllable:value.runtime.controllable, reason:value.runtime.reason },
    host: { state:value.host.state, detected:value.host.detected, processRunning:value.host.processRunning, version:value.host.version, reason:value.host.reason },
    bridges:value.bridges.map(({id,state,reason})=>({id,state,reason})),
    capabilities:value.capabilities.map(({id,state,confidence,backend,notes})=>({id,state,confidence,backend,notes:redact(notes)})) };
}
export class MockAdapter {
  constructor(scenario = 'disconnected') { this.setScenario(scenario); this.runtimeState = 'stopped'; }
  setScenario(scenario) { if (!mockScenarios.includes(scenario)) throw new AppError('INVALID_SCENARIO', 'backend'); this.scenario = scenario; }
  async snapshot() {
    if (['offline','timeout','backend-error'].includes(this.scenario)) throw new AppError({ offline:'BACKEND_OFFLINE', timeout:'BACKEND_TIMEOUT', 'backend-error':'BACKEND_ERROR' }[this.scenario], 'backend');
    const state = this.scenario === 'connected' ? 'connected' : this.scenario === 'degraded' ? 'degraded' : 'disconnected';
    return { apiVersion: 1, runtime: { state: this.scenario === 'faulted' ? 'faulted' : this.runtimeState, version: 'mock-v1', controllable: true, reason: 'DEVELOPMENT_MOCK' },
      host: { state, detected: state !== 'disconnected', processRunning: state !== 'disconnected', version: state === 'disconnected' ? null : 'mock-v1', reason: 'DEVELOPMENT_MOCK' },
      bridges: ['controller','gopher','mcp','sysex'].map(id => ({ id, state: this.scenario === 'degraded' && id === 'mcp' ? 'degraded' : state, reason: 'DEVELOPMENT_MOCK' })),
      capabilities: [ { id: 'mixer.track.read', state: 'available', confidence: 'high', backend: 'mock', notes: ['DEVELOPMENT MOCK'] },
        { id: 'plugin.enumerate', state: 'partial', confidence: 'high', backend: 'mock', notes: ['DEVELOPMENT MOCK'] },
        ...['plugin.parameter.layout','plugin.parameter.read','plugin.parameter.write'].map(id => ({ id, state: 'experimental', confidence: 'high', backend: 'mock', notes: ['DEVELOPMENT MOCK'] })),
        { id: 'plugin.write.verification', state: 'unavailable', confidence: 'unknown', backend: 'mock', notes: ['DEVELOPMENT MOCK'] } ] };
  }
  async control(action) { if (this.scenario === 'faulted' && action === 'start') throw new AppError('MOCK_RUNTIME_FAILURE', 'runtime'); this.runtimeState = action === 'start' ? 'starting' : 'stopping'; await new Promise(resolve => setTimeout(resolve, 200)); this.runtimeState = action === 'start' ? 'running' : 'stopped'; return (await this.snapshot()).runtime; }
}
export class RealAdapter {
  constructor({ python = 'python', cwd, timeoutMs = 10000, spawnProcess = spawn } = {}) { Object.assign(this, { python, cwd, timeoutMs, spawnProcess }); this.children = new Set(); this.closed = false; }
  snapshot(config) { return this.query(config, 'status'); }
  detectPath(config) { return this.query(config, 'detectPath'); }
  query(config, operation) {
    if (this.closed) return Promise.reject(new AppError('BACKEND_OFFLINE', 'backend'));
    return new Promise((resolve, reject) => {
      const child = this.spawnProcess(this.python, ['-m','dawloop.desktop_status'], { cwd: this.cwd, windowsHide: true,
        env: { ...process.env, PYTHONUTF8:'1', PYTHONPATH: `${this.cwd}/src` }, stdio: ['pipe','pipe','pipe'] });
      this.children.add(child); let output = ''; let finished = false;
      const finish = (error, value) => { if (finished) return; finished = true; clearTimeout(timer); this.children.delete(child); error ? reject(error) : resolve(value); };
      const timer = setTimeout(() => { child.kill(); finish(new AppError('BACKEND_TIMEOUT', 'backend')); }, this.timeoutMs);
      child.once('error', () => finish(new AppError('BACKEND_OFFLINE', 'backend')));
      child.stderr.on('data', () => {});
      child.stdin.on('error', () => {});
      child.stdout.on('data', chunk => { output += chunk.toString('utf8'); if (output.length > 512 * 1024) { child.kill(); finish(new AppError('RESPONSE_TOO_LARGE', 'backend')); } });
      child.once('close', code => {
        if (finished) return;
        try {
          if (code !== 0) throw Error(); const envelope = JSON.parse(output);
          if (envelope.apiVersion !== 1 || envelope.ok !== true) throw Error();
          const data = envelope.data;
          if (operation === 'detectPath' && !(data?.executablePath === null || typeof data?.executablePath === 'string')) throw Error();
          finish(null, operation === 'status' ? validateSnapshot(data) : data);
        }
        catch { finish(new AppError('INVALID_BACKEND_RESPONSE', 'backend')); }
      });
      child.stdin.end(JSON.stringify({ apiVersion: 1, operation, executablePath: config.host.executablePath, detectHost: config.general.detectHostOnStartup }));
    });
  }
  async control() { throw new AppError('RUNTIME_CONTROL_UNAVAILABLE', 'runtime'); }
  close() { this.closed = true; for (const child of this.children) child.kill(); this.children.clear(); }
}
