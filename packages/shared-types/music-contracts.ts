import type {Result} from './contracts';
import type {MusicAnalysisResultV0_5} from './analysis-contracts';
export interface Note {id?:string;pitch:number;start:number;duration:number;velocity:number;part:number}
export interface SymbolicScore {schemaVersion:1;tempo:number;meter:number[];tempoMap:{start:number;bpm:number}[];notes:Note[];source:string;edits:unknown[];abc?:string;pitchBends?:{start:number;value:number;part:number}[];provenance?:Record<string,unknown>;chords?:{start:number;duration:number;degree:number;pitches:number[]}[]}
export interface Asset {visibility?:'SESSION_IMPORT'|'USER_SAVED_PROJECT'|'USER_SAVED_ANALYSIS';id:string;name:string;sha256:string;bytes:number;extension:string;collection:string}
export interface Analysis {schemaVersion:1;analysisId?:string;assetId:string;sourceSha256:string;duration:number;sampleRate:number;channels:number;format:string;waveform:number[];bpmCandidates:number[];energy:number[][];spectralCentroid:number[][];beats:number[];onsets:number[];chroma:number[];segmentCandidates:number[];bpmConfidence:string;profile:{userDescription:string;[key:string]:unknown}}
export type AnalysisLifecycle='READY'|'PROCESSING'|'FAILED'|'UNKNOWN'|'SOURCE_MISSING';
export interface AnalysisVersion {analysisId:string;analysisVersion:string|null;state:AnalysisLifecycle;reasonCode:string|null;modelRevision:string|null;observedAt:string|null;startedAt:string|null}
export interface AnalysisEdit {editId:string;sourceAnalysisId:string|null;createdAt:string|null;state:'READY'|'UNKNOWN';reasonCode?:string}
export interface AnalysisAssetEntry {assetId:string;sourceSha256:string;fileReference:string;state:AnalysisLifecycle;reasonCode:string|null;lastObserved:string|null;latestAnalysisId?:string|null;versions:AnalysisVersion[];edits:AnalysisEdit[]}
export interface AnalysisRecovery {assetId:string;state:AnalysisLifecycle;reasonCode:string|null;analysis:Analysis|null;record:MusicAnalysisResultV0_5|null;legacyProfile:{format:'LEGACY_MI_0_4';data:{userDescription?:string};missingEvidence:string[];evidenceStatus:string}|null;versions:AnalysisVersion[];edits:AnalysisEdit[]}
export interface Job {id:string;method:string;state:string;progress:number;downloadedBytes?:number;totalBytes?:number;error:string|null;detail?:string;result:Analysis|SymbolicScore|unknown}
export interface Model {id:string;modelId:string;status:string;reason:string;license:string;revision:string|null;device:string;bytes?:number;requiredBytes?:number|null;downloadBytes?:number;freeBytes?:number;support?:string}
export interface SetupProvider {id:string;license:string;codeLicense?:string;downloadBytes:number|null;runtimeDownloadBytes?:number|null;weightBytes?:number|null;minimumStorageBytes:number;freeBytes:number;diskEligible:boolean;installable:boolean;downloadingDependenciesKnown:boolean;qualification:string;reason:string}
export interface SetupStatus {schemaVersion:1;completed:boolean;skipped:boolean;offlineModelUploads:false;providers:SetupProvider[];hardware:{cpu?:string;ramBytes:number;freeRamBytes:number;platform:string;osRelease:string;arch:string;gpu:{name:string;memoryMiB:number;driver:string}|null;wsl:string[]|null;python:{role:string;configured:boolean;version?:string;verified:boolean}[]}}
export interface AudioSetupStatus {state:'READY'|'NOT_READY';componentState?:'READY'|'INSTALL_REQUIRED'|'INSTALLING'|'FAILED'|'NOT_SUPPORTED';resources:{id:string;license:string;additionalBytes:number;kind:'EXISTING_MANAGED_ENVIRONMENT'}[];offlineInstallAvailable:boolean;reasonCode:string|null;component?:{id:string;version:string;archiveBytes:number;installedBytes:number;minimumFreeBytes:number;license:string;licenseReview:string};job?:{id:string;state:string;error:string|null;activationCommitted:boolean}|null}
export interface SavedScore {schemaVersion:1;id:string;name:string;savedAt:string;category:'USER_EDITED';score:SymbolicScore}
export interface MusicBridge {
  savedScores():Promise<Result<SavedScore[]>>;
  saveScore(p:{score:SymbolicScore;name:string}):Promise<Result<SavedScore>>;
  audioSetupStatus():Promise<Result<AudioSetupStatus>>;
  connectLocalAudioRuntime(p:{resourceId:string}):Promise<Result<{state:'READY'|'NOT_READY';reasonCode:string|null}>>;
  archivedAssets():Promise<Result<Asset[]>>;
  basicStatus():Promise<Result<{state:'READY'|'NOT_READY';reasonCode:string|null;version?:string}>>;
  configureAudioRuntime():Promise<Result<{state:'READY'|'NOT_READY';reasonCode:string|null}|null>>;
  saveAsset(p:{assetId:string;kind:'USER_SAVED_PROJECT'|'USER_SAVED_ANALYSIS';analysisId?:string}):Promise<Result<boolean>>;
  dismiss(p:{id:string}):Promise<Result<boolean>>;
  reviewOffsets(p:{assetId:string;score:SymbolicScore}):Promise<Result<string>>;
  setupStatus():Promise<Result<SetupStatus>>;
  setupFinish(p:{skipped:boolean}):Promise<Result<boolean>>;
  setupInstall(p:{models:{id:string;license:string;codeLicense?:string}[]}):Promise<Result<string>>;
  openYueExperience():Promise<Result<boolean>>;
  status(p?:{assetId?:string;analysisId?:string}):Promise<Result<{assets:Asset[];jobs:Job[];registry?:{schemaVersion:'0.5A';assets:AnalysisAssetEntry[]};recovered?:AnalysisRecovery|null}>>;
  models():Promise<Result<Model[]>>;
  jobs():Promise<Result<Job[]>>;
  importAudio():Promise<Result<Asset|null>>;
  importAbc():Promise<Result<string|null>>;
  importMidi():Promise<Result<string|null>>;
  analyze(p:{assetId:string;range?:{start?:number;end?:number}}):Promise<Result<string>>;
  cancel(p:{id:string}):Promise<Result<boolean>>;
  install(p:{modelId:string;licenseAccepted:string}):Promise<Result<string>>;
  modelDiagnostics():Promise<Result<boolean|null>>;
  check(p:{modelId:string}):Promise<Result<Model[]>>;
  verify(p:{modelId:string}):Promise<Result<string>>;
  load(p:{modelId:string}):Promise<Result<string>>;
  unload(p:{modelId:string}):Promise<Result<boolean>>;
  abc(p:{text:string}):Promise<Result<SymbolicScore>>;
  profile(p:{assetId:string;profile:Analysis['profile'];sourceAnalysisId?:string}):Promise<Result<boolean>>;
  preview(p:{assetId:string}):Promise<Result<string>>;
  releasePreview(p:{assetId:string;url:string}):Promise<Result<boolean>>;
  waveform(p:{assetId:string}):Promise<Result<string>>;
  removeAsset(p:{assetId:string}):Promise<Result<boolean>>;
  collection(p:{assetId:string;name:string}):Promise<Result<boolean>>;
  exportMidi(p:{score:SymbolicScore}):Promise<Result<string|null>>;
  extractEmbedding(p:{assetId:string}):Promise<Result<string>>;
  transcribe(p:{assetId:string;engine?:string;tempo?:number}):Promise<Result<string>>;
  generate(p:{style:string;seed:number;mode:string;abc?:string;profile?:Analysis['profile'];tempo?:number;confirmed?:boolean;engine?:string;key?:number;scale?:string;meter?:number[];progression?:string;density?:number;rhythm?:string;bars?:number;energyCurve?:number[];candidates?:number}):Promise<Result<string>>;
}
