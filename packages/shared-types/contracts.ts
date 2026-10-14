export type ConnectionState = 'unknown' | 'checking' | 'connected' | 'disconnected' | 'degraded' | 'error';
export type RuntimeState = 'unknown' | 'stopped' | 'starting' | 'running' | 'stopping' | 'faulted';
export type CapabilityState = 'available' | 'partial' | 'experimental' | 'unavailable' | 'unknown';
export type BackendMode = 'real' | 'mock';
export type Language = 'zh-CN' | 'en-US';
export interface DawLoopError { code: string; category: string; message: string; recoverable: boolean }
export type Result<T> = { apiVersion: 1; ok: true; data: T } | { apiVersion: 1; ok: false; error: DawLoopError };
export type Confidence = 'high' | 'medium' | 'low' | 'very-low' | 'unknown';
export interface Capability { id: string; state: CapabilityState; confidence: Confidence; backend: string; notes: string[] }
export interface RuntimeStatus { state: RuntimeState; version: string | null; controllable: boolean; reason: string }
export interface HostStatus { state: ConnectionState; detected: boolean | null; processRunning: boolean | null; version: string | null; reason: string }
export interface BridgeStatus { id: string; state: ConnectionState; reason: string }
export interface Config {
  schemaVersion: 1; activeProfileId: string;
  general: { launchAtLogin: boolean; detectHostOnStartup: boolean; autoStartRuntime: boolean; logLevel: 'Normal' | 'Detailed' | 'Debug'; [key: string]: unknown };
  host: { executablePath: string; [key: string]: unknown };
  ui?: { reducedMotion?:boolean; language?: Language; onboardingCompleted?:boolean; mode?:'USER_MODE'|'DEVELOPER_MODE'; [key: string]: unknown };
  features: { experimentalMixerWrite: boolean; pluginParameterEditing: boolean; nativeGopherTransport: boolean; [key: string]: unknown };
  [key: string]: unknown;
}
export interface Profile {
  schemaVersion: 1; id: string; name: string;
  runtime: Record<string, unknown>; verification: { preset?: 'Strict' | 'Balanced' | 'Fast' | 'Custom'; [key: string]: unknown };
  agent: Record<string, unknown>; mixer: Record<string, unknown>; ui: Record<string, unknown>;
  [key: string]: unknown;
}
export interface LogEntry { sequence: number; timestamp: string; level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG'; source: string; message: string }
export interface AppStatus { apiVersion: 1; appVersion: string; backend: BackendMode; label: string; observedAt: string; runtime: RuntimeStatus; host: HostStatus; bridges: BridgeStatus[]; capabilities: Capability[]; errors: DawLoopError[] }
export interface CoreAdapterV1 {
  getAppStatus(): Promise<Result<AppStatus>>;
  getRuntimeStatus(): Promise<Result<RuntimeStatus>>;
  getHostStatus(): Promise<Result<HostStatus>>;
  getBridgeStatus(): Promise<Result<BridgeStatus[]>>;
  getCapabilities(): Promise<Result<Capability[]>>;
  startRuntime(): Promise<Result<RuntimeStatus>>;
  stopRuntime(): Promise<Result<RuntimeStatus>>;
  getConfig(): Promise<Result<Config>>;
  updateConfig(patch: Partial<Config>): Promise<Result<Config>>;
  getProfiles(): Promise<Result<Profile[]>>;
  createProfile(name: string): Promise<Result<Profile>>;
  updateProfile(profile: Profile): Promise<Result<Profile>>;
  getActiveProfile(): Promise<Result<Profile>>;
  setActiveProfile(id: string): Promise<Result<Profile>>;
  getDiagnostics(): Promise<Result<Record<string, unknown>>>;
  getRecentLogs(): Promise<Result<LogEntry[]>>;
}
export type MockScenario = 'connected' | 'disconnected' | 'degraded' | 'faulted' | 'offline' | 'timeout' | 'backend-error';
export type ConfigPatch = { general?: Partial<Config['general']>; host?: Partial<Config['host']>; ui?: Config['ui']; features?: Partial<Config['features']> };
export interface WorldSnapshot {
  presentation?: 'real-live' | 'real-cached' | 'development-mock' | 'unavailable';
  history?: {reason:string;at:string;sequence:number}[];
  publisher?: Pick<MixerSnapshotV1,'schemaVersion'|'snapshotId'|'observationId'|'sequence'|'publishedAt'|'sourceBackend'|'freshness'|'levels'|'reasonCodes'>;
  apiVersion: 1; source: 'core' | 'mock'; state: 'unknown' | 'current' | 'stale'; reason: string; observedAt: string | null;
  session: {hostId:string;sessionId:string;projectGeneration:string;projectName:string|null} | null;
  target: {trackIndex:number;slotIndex:number;instanceId:string|null} | null;
  tracks: {index:number;name:string;slots:{index:number;state:'empty'|'occupied'|'unknown';plugin:{instanceId:string|null;name:string;parameterCount:number|null;parameters:{index:number;name:string;value:number|null;readState:string}[];identityVerified:boolean;layoutReadable:boolean;valuesReadable:boolean;writeEnabled:false}|null}[]}[];
  capabilities: {id:string;state:CapabilityState;confidence:Confidence;contractVersion:1|null;evidence:{id:string;sha256:string;outcome:string;observedAt:string;binding:Record<string,unknown>}[];promotion:{coreExists:boolean;liveEvidence:boolean;contractStable:boolean;adapterExposed:boolean;rendererAllowed:boolean;enabled:boolean}}[];
}
export type SnapshotLevel = 'available' | 'partial' | 'not-ready' | 'unknown';
export interface MixerSessionBinding { session_id:string; project_generation:string; host_generation:string }
export interface MixerTargetBinding extends MixerSessionBinding {
  operation_id:string; controller_build_id:string; mixer_track:number; effect_slot:number; raw_plugin_name:string; api_version:number;
}
export interface MixerSnapshotV1 {
  schemaVersion:1; snapshotId:string; sessionId:string|null; observationId:string; sequence:number; observedAt:string; publishedAt:string;
  sourceBackend:'local-observer'|'validated-core'; freshness:{maxAgeMs:15000;state:'current'|'stale'};
  sessionBinding:MixerSessionBinding|null; targetBinding:MixerTargetBinding|null;
  pluginIdentity:{instanceId:string|null;rawPluginName:string;format:string|null;continuity:'verified'|'unknown'}|null;
  levels:Record<'session'|'structure'|'identity'|'layout'|'values',SnapshotLevel>;
  tracks:CoreMixerTrack[]; capabilityEvidence:Omit<WorldSnapshot['capabilities'][number],'promotion'>[]; errors:string[]; reasonCodes:string[];
  world: {apiVersion:1;source:'core';observedAt:string;session:NonNullable<WorldSnapshot['session']>;target:WorldSnapshot['target'];tracks:CoreMixerTrack[];capabilities:MixerSnapshotV1['capabilityEvidence']}|null;
  connection:{runtime:RuntimeStatus;host:HostStatus;bridges:BridgeStatus[]}|null;
}
export interface CoreMixerTrack {
  index:number; name:string; slots:{index:number;state:'empty'|'occupied'|'unknown';plugin:{instanceId:string|null;name:string;parameterCount:number|null;parameters:{index:number;name:string;value:number|null;readState:'available'|'unknown'|'unavailable'}[]}|null}[];
}
export interface DesktopMethodMap {
  getWorldSnapshot: {params:undefined;result:WorldSnapshot};
  getDesktopEnvironment: { params: undefined; result: DesktopEnvironment };
  getAppStatus: { params: undefined; result: AppStatus };
  getRuntimeStatus: { params: undefined; result: RuntimeStatus };
  getHostStatus: { params: undefined; result: HostStatus };
  getBridgeStatus: { params: undefined; result: BridgeStatus[] };
  getCapabilities: { params: undefined; result: Capability[] };
  startRuntime: { params: undefined; result: RuntimeStatus };
  stopRuntime: { params: undefined; result: RuntimeStatus };
  getConfig: { params: undefined; result: Config };
  updateConfig: { params: ConfigPatch; result: Config };
  getProfiles: { params: undefined; result: Profile[] };
  createProfile: { params: string; result: Profile };
  updateProfile: { params: Profile; result: Profile };
  getActiveProfile: { params: undefined; result: Profile };
  setActiveProfile: { params: string; result: Profile };
  getDiagnostics: { params: undefined; result: Record<string, unknown> };
  getRecentLogs: { params: undefined; result: LogEntry[] };
  testHostPath: { params: string | undefined; result: { valid: boolean; reason: string } };
  detectHostPath: { params: undefined; result: { executablePath: string | null } };
  setBackend: { params: BackendMode; result: AppStatus };
  setMockScenario: { params: MockScenario; result: AppStatus };
}
export type DesktopArgs<K extends keyof DesktopMethodMap> = undefined extends DesktopMethodMap[K]['params'] ? [params?: DesktopMethodMap[K]['params']] : [params: DesktopMethodMap[K]['params']];
export interface DesktopEnvironment {
  reducedMotion?:boolean;
  systemLocale:string; language:Language; languageExplicit:boolean; development:boolean;
  packaged?:boolean; appVersion?:string; electronVersion?:string; nodeVersion?:string; releaseChannel?:'internal'|'development'|'stable'|'preview';
  dependencies?:{core:'desktop-only'|'unavailable';python:'not-bundled'|'development-external';controller:'not-probed'|'not-found'|'unavailable'|'present-unverified';host:'user-installed'};
}
export interface DesktopUpdateView {
  version:string;preferences:{enabled:boolean;channel:'stable'|'preview';notifications:boolean};checkedAt:number|null;
  status:'UPDATE_AVAILABLE'|'UP_TO_DATE'|'CHECK_FAILED'|'CHECK_DISABLED'|'UNKNOWN';
  release:null|{version:string;publishedAt:string;notes:string};publicPush:'APPROVED'|'DISABLED';snoozeUntil:number;
}
export interface DesktopBridge {
  updates: {get(params?:object):Promise<Result<DesktopUpdateView>>;
    check(params?:object):Promise<Result<DesktopUpdateView>>;
    configure(params?:object):Promise<Result<DesktopUpdateView>>;
    snooze(params?:object):Promise<Result<DesktopUpdateView>>;
    open(params?:object):Promise<Result<boolean>>};
  music: import('./music-contracts').MusicBridge;
  call<K extends keyof DesktopMethodMap>(method: K, ...args: DesktopArgs<K>): Promise<Result<DesktopMethodMap[K]['result']>>;
  copy(text: string): Promise<Result<null>>;
  browseHost(): Promise<Result<string | null>>;
  exportDiagnostics(): Promise<Result<{ saved:boolean }>>;
}
declare global { interface Window { dawloop: DesktopBridge } }
