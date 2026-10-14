import fs from 'node:fs/promises';
import path from 'node:path';
import { ConfigService, AppError, object, atomicWrite } from '../config/index.mjs';
import { ProfileService } from '../profiles/index.mjs';
import { LogService } from '../logging/index.mjs';
import { diagnosticReport } from '../diagnostics/index.mjs';
import { MockAdapter, RealAdapter, unavailable } from '../core-adapter/index.mjs';
import { readWorld, unknownWorld, promotion } from '../core-adapter/world.mjs';
import { MixerSnapshotPublisher, localObservation } from '../core-snapshot/index.mjs';
import { PublishedMixerAdapter } from '../core-adapter/published.mjs';

const methods = new Set(['getWorldSnapshot','getAppStatus','getRuntimeStatus','getHostStatus','getBridgeStatus','getCapabilities','startRuntime','stopRuntime','getConfig','updateConfig','getProfiles','createProfile','updateProfile','getActiveProfile','setActiveProfile','getDiagnostics','getRecentLogs','setBackend','setMockScenario','testHostPath','detectHostPath']);
const mutations = new Set(['updateConfig','createProfile','updateProfile','setActiveProfile']);
const controls = new Set(['startRuntime','stopRuntime','setBackend','setMockScenario']);
export class AppCore {
  constructor({ roamingRoot, localRoot, cwd, python, appVersion = '0.1.0-desktop', mode = 'real', scenario, timeoutMs, realAdapter, development = false, worldFile, trustedReadSource } = {}) {
    if (mode === 'mock' && !development) throw new AppError('METHOD_UNAVAILABLE', 'protocol');
    this.config = new ConfigService(roamingRoot); this.profiles = new ProfileService(roamingRoot); this.logs = new LogService(localRoot);
    this.localRoot = localRoot; this.mode = mode; this.mock = new MockAdapter(scenario); this.real = realAdapter ?? new RealAdapter({ cwd, python, timeoutMs });
    this.worldFile = worldFile; this.development = development; this.mutationQueue = Promise.resolve(); this.controlQueue = Promise.resolve(); this.pending = new Set(); this.observation = null;
    this.appVersion = appVersion; this.cached = null; this.closed = false;
    this.publisher = new MixerSnapshotPublisher({source:trustedReadSource ?? {
      sourceBackend:'local-observer', read:()=>localObservation(this.cached), verify:observation=>{
        if (observation.world!==null || observation.sessionBinding!==null || observation.targetBinding!==null || observation.pluginIdentity!==null) return false;
        const status=this.cached;
        return status?.backend==='real'
          ? observation.observedAt===status.observedAt && observation.levels.session==='partial' && JSON.stringify(observation.connection)===JSON.stringify({runtime:status.runtime,host:status.host,bridges:status.bridges})
          : observation.connection===null && observation.levels.session==='unknown';
      },
      currentBinding:()=>({connected:!this.closed && this.mode==='real',sessionBinding:null,targetBinding:null,instanceId:null})
    }});
    this.publishedAdapter = new PublishedMixerAdapter(this.publisher);
  }
  async initialize() {
    await this.logs.initialize();
    // 首次默认文件创建先完成，避免并发读取与修改争抢初始化写入。
    try { await this.config.get(); await this.profiles.get('default'); } catch {}
    await this.logs.emit('Desktop', 'INFO', 'DESKTOP_STARTED');
  }
  call(method, params) {
    const lane = mutations.has(method) ? 'mutationQueue' : controls.has(method) ? 'controlQueue' : null;
    const job = (lane ? this[lane] : Promise.resolve()).then(async () => {
      try {
        if (this.closed || !methods.has(method)) throw new AppError('METHOD_UNAVAILABLE', 'protocol');
        if (!this.development && ['setBackend','setMockScenario'].includes(method)) throw new AppError('METHOD_UNAVAILABLE', 'protocol');
        const data = await this.dispatch(method, params); return { apiVersion: 1, ok: true, data };
      } catch (error) {
        const safe = error instanceof AppError ? { code: error.code, category: error.category, message: error.message, recoverable: true }
          : { code: 'INTERNAL_ERROR', category: 'internal', message: 'INTERNAL_ERROR', recoverable: true };
        try { await this.logs.emit('Desktop', 'ERROR', safe.code); } catch {}
        return { apiVersion: 1, ok: false, error: safe };
      }
    });
    if (lane) this[lane] = job.then(() => {});
    this.pending.add(job); void job.then(() => this.pending.delete(job)); return job;
  }
  status() {
    if (this.closed) throw new AppError('METHOD_UNAVAILABLE', 'protocol');
    if (this.observation?.mode === this.mode) return this.observation.promise;
    const mode = this.mode;
    const observation = { mode, promise: this.observe(mode) };
    this.observation = observation;
    const clear = () => { if (this.observation === observation) this.observation = null; };
    void observation.promise.then(clear, clear);
    return observation.promise;
  }
  async observe(mode) {
    let config, snapshot; const errors = [];
    try { config = await this.config.get(); }
    catch (error) { errors.push({ code: error instanceof AppError ? error.code : 'CONFIG_UNREADABLE', category:'configuration', message:'CONFIG_UNAVAILABLE', recoverable:true }); }
    if (config) {
      try { snapshot = await (mode === 'mock' ? this.mock : this.real).snapshot(config); }
      catch (error) { errors.push({ code: error instanceof AppError ? error.code : 'BACKEND_ERROR', category: 'backend', message: 'STATUS_UNAVAILABLE', recoverable: true }); }
    }
    snapshot ??= unavailable();
    const result = { apiVersion: 1, appVersion: this.appVersion, backend: mode, label: mode === 'mock' ? 'DEVELOPMENT_MOCK' : 'REAL_READ_ONLY', observedAt: new Date().toISOString(), ...snapshot, errors };
    if (mode === this.mode) this.cached = result;
    return result;
  }
  async world() {
    if (this.mode === 'real' && !(this.development && this.worldFile)) return this.publishedAdapter.world();
    let world;
    try { world = this.mode === 'real' ? await readWorld(this.worldFile) : { ...unknownWorld(), source:'mock' }; }
    catch { world = { ...unknownWorld(), reason:'WORLD_SNAPSHOT_REJECTED' }; }
    const selected = world.target;
    const capabilities = world.capabilities.map(c => ({ ...c, promotion:promotion(world,c.id,['plugin.identity.read','plugin.parameter.layout','plugin.parameter.read'].includes(c.id) ? selected : null) }));
    const trackAllowed=promotion(world,'mixer.track.read').enabled;
    const enumerateAllowed=promotion(world,'plugin.enumerate').enabled;
    const tracks=trackAllowed ? world.tracks.map(t=>({...t,slots:enumerateAllowed ? t.slots.map(slot=> {
      if (!slot.plugin) return slot;
      const target={trackIndex:t.index,slotIndex:slot.index,instanceId:slot.plugin.instanceId};
      const layout=promotion(world,'plugin.parameter.layout',target).enabled;
      const readable=promotion(world,'plugin.parameter.read',target).enabled;
      return {...slot,plugin:{...slot.plugin,parameterCount:layout ? slot.plugin.parameterCount : null,parameters:layout ? slot.plugin.parameters.map(p=>({...p,value:readable && p.readState==='available' ? p.value : null,readState:readable ? p.readState : 'unavailable'})) : [], identityVerified:promotion(world,'plugin.identity.read',target).enabled,layoutReadable:layout,valuesReadable:readable,writeEnabled:false}};
    }) : []})) : [];
    return {...world,source:'mock',presentation:'development-mock',tracks,capabilities};
  }
  async dispatch(method, params) {
    switch (method) {
      case 'getWorldSnapshot': return this.world();
      case 'getAppStatus': return this.status();
      case 'getRuntimeStatus': return (await this.status()).runtime;
      case 'getHostStatus': return (await this.status()).host;
      case 'getBridgeStatus': return (await this.status()).bridges;
      case 'getCapabilities': return (await this.status()).capabilities;
      case 'startRuntime': case 'stopRuntime': {
        const result = await (this.mode === 'mock' ? this.mock : this.real).control(method === 'startRuntime' ? 'start' : 'stop');
        await this.logs.emit('Runtime', 'INFO', `${this.mode === 'mock' ? 'MOCK_' : ''}RUNTIME_${result.state.toUpperCase()}`); return result;
      }
      case 'getConfig': return this.config.get();
      case 'updateConfig': {
        if (!object(params) || 'activeProfileId' in params) throw new AppError('INVALID_CONFIG_PATCH');
        const result = await this.config.update(params); await this.logs.emit('Desktop', 'INFO', 'CONFIG_SAVED'); return result;
      }
      case 'getProfiles': return this.profiles.list();
      case 'createProfile': { const result = await this.profiles.create(params); await this.logs.emit('Desktop','INFO','PROFILE_CREATED'); return result; }
      case 'updateProfile': return this.profiles.update(params);
      case 'getActiveProfile': return this.profiles.get((await this.config.get()).activeProfileId);
      case 'setActiveProfile': { const result = await this.profiles.get(params); await this.config.update({ activeProfileId: result.id }); await this.logs.emit('Desktop', 'INFO', 'PROFILE_SWITCHED'); return result; }
      case 'getDiagnostics': {
        const status = await this.status(); let config = null;
        try { config = await this.config.get(); } catch {}
        const report = diagnosticReport(status, config, await this.world());
        await fs.mkdir(path.join(this.localRoot, 'diagnostics'), { recursive: true });
        await atomicWrite(path.join(this.localRoot, 'diagnostics', 'latest.json'), report);
        await this.logs.emit('Desktop', 'INFO', 'DIAGNOSTICS_GENERATED'); return report;
      }
      case 'getRecentLogs': return this.logs.recent();
      case 'detectHostPath': if (this.mode === 'mock') return { executablePath: null }; return this.real.detectPath(await this.config.get());
      case 'setBackend': if (!['real','mock'].includes(params)) throw new AppError('INVALID_BACKEND','protocol'); this.publisher.invalidate('BACKEND_CHANGED'); this.mode = params; this.cached = null; this.observation = null; await this.logs.emit('Desktop','WARN', params === 'mock' ? 'MOCK_ENABLED' : 'REAL_OBSERVER_SELECTED'); return this.status();
      case 'setMockScenario': if (this.mode !== 'mock') throw new AppError('MOCK_ONLY','protocol'); this.mock.setScenario(params); this.observation = null; return this.status();
      case 'testHostPath': {
        const candidate = params === undefined ? (await this.config.get()).host.executablePath : params;
        if (typeof candidate !== 'string') throw new AppError('INVALID_PATH');
        if (!candidate || !path.isAbsolute(candidate) || path.basename(candidate).toLowerCase() !== 'fl64.exe') return { valid: false, reason: 'HOST_PATH_REQUIRED' };
        try { return { valid: (await fs.stat(candidate)).isFile(), reason: 'HOST_PATH_EXISTS_ONLY' }; } catch { return { valid: false, reason: 'HOST_PATH_INACCESSIBLE' }; }
      }
    }
  }
  async close() { this.closed = true; this.publisher.close(); this.real.close(); await Promise.all([...this.pending]); }
}
