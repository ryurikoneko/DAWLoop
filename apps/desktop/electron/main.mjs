import { app, BrowserWindow, ipcMain, dialog, clipboard, Tray, Menu, nativeImage, net, protocol, shell, Notification } from 'electron';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { MusicIntelligenceService } from '../../../packages/music-intelligence/service.mjs';
import {managedRuntime} from '../../../packages/music-intelligence/managed-runtime.mjs';
import { AppCore } from '../../../packages/app-core/index.mjs';
import { startTrustedSessionWorker } from '../../../packages/core-session/worker.mjs';
import { resolveLanguage } from '../../../packages/config/language.mjs';
import { nativeTranslations } from './native-i18n.mjs';
import { desktopDevelopment, rendererMethodAllowed } from './renderer-policy.mjs';
import { exportDiagnosticReport } from './diagnostic-export.mjs';
import { observerPython, productEnvironment, safeStartupRecord } from './product-environment.mjs';
import { DesktopUpdates } from '../../../packages/desktop-updates/service.mjs';
import {TranscriptionStudio} from '../../../packages/music-intelligence/transcription-studio.mjs';
import { StyleLabBridge } from './style-lab.mjs';
import { windowsNotifier } from './update-toast.mjs';
protocol.registerSchemesAsPrivileged([{scheme:"dawloop-audio",privileges:{standard:true,secure:true,stream:true,corsEnabled:true}}]);
if(process.platform==='win32')app.setAppUserModelId('DAWLoop.Desktop.Internal');
const development = desktopDevelopment(app.isPackaged, process.argv);

const directory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(directory, '../../..');
let packagedChannel;
try {packagedChannel=JSON.parse(fs.readFileSync(path.join(app.getAppPath(),'package.json'),'utf8')).dawloopReleaseChannel;}catch{}
const product = productEnvironment({ isPackaged:app.isPackaged, root, version:app.getVersion(), releaseChannel:packagedChannel, electronVersion:process.versions.electron, nodeVersion:process.versions.node, documents:app.getPath('documents'), appData:app.getPath('appData') });
const testingOverride = process.env.DAWLOOP_DESKTOP_DATA_ROOT;
const override = testingOverride || (app.getVersion().includes('transcription') ? path.join(app.getPath('appData'),'DAWLoop','TranscriptionStudio') : undefined);
if (override) {
  const browserData = path.join(override, 'electron');
  fs.mkdirSync(browserData, { recursive:true });
  app.setPath('userData', browserData);
}
let studio;let music;let styleLab;let desktopInitialization;let updates;let updateTimer;
const brandIcon=path.resolve(directory,'../dist/brand/DAWLoop.ico');
let window, core, tray, translations, sessionWorker, sessionStartup, sessionInvalidation, sessionUnsubscribe; let quitting = false;
let lastDiagnosticText, exporting = false;
const failure = () => ({ apiVersion: 1, ok: false, error: { code: 'IPC_REJECTED', category: 'protocol', message: 'IPC_REJECTED', recoverable: true } });
function updateTray() {
  tray?.setContextMenu(Menu.buildFromTemplate([{ label:translations.t('native.show'), click:()=>window.show() }, { label:translations.t('native.quit'), click:()=>app.quit() }]));
}
const trusted = event => event.sender === window?.webContents && event.senderFrame === window.webContents.mainFrame;
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { window?.show(); window?.focus(); });
  app.whenReady().then(async () => {
    const systemLocale = app.getSystemLocale();
    translations = nativeTranslations(resolveLanguage(undefined, systemLocale), development);
    const roamingRoot = override ? path.join(override, 'roaming') : path.join(app.getPath('appData'), 'DAWLoop');
    const localRoot = override ? path.join(override, 'local') : path.join(process.env.LOCALAPPDATA || app.getPath('userData'), 'DAWLoop');
    updates=new DesktopUpdates({file:path.join(localRoot,'Updates','state.json'),version:product.appVersion,
      buildChannel:product.releaseChannel,fetcher:(url,options)=>net.fetch(url,options),open:url=>shell.openExternal(url),
      notify:windowsNotifier(Notification,brandIcon),language:()=>translations.language});
    const sessionIndex=process.argv.indexOf('--core-session-spec');
    let sessionSpec;
    if(sessionIndex!==-1) {
      if(app.isPackaged || development || !process.argv[sessionIndex+1]) throw Error('SESSION_SOURCE_REJECTED');
      sessionSpec=JSON.parse(fs.readFileSync(process.argv[sessionIndex+1],'utf8'));
    }
    const sessionSource=sessionSpec ? {sourceBackend:'validated-core',read:()=>{
      if(!sessionWorker)throw Object.assign(new Error('SESSION_SOURCE_UNAVAILABLE'),{code:'SESSION_SOURCE_UNAVAILABLE'});
      return sessionWorker.source.read();
    },verify:observation=>sessionWorker?.source.verify(observation)??false,currentBinding:()=>sessionWorker?.source.currentBinding()??{connected:false},
    onInvalidation:listener=>{sessionInvalidation=listener;return()=>{sessionInvalidation=null;sessionUnsubscribe?.();};}} : undefined;
    core = new AppCore({ roamingRoot, localRoot, cwd: root, python:observerPython(app.isPackaged, process.resourcesPath, process.env), worldFile:app.isPackaged ? undefined : process.env.DAWLOOP_CORE_WORLD_SNAPSHOT, appVersion:product.appVersion, development, trustedReadSource:sessionSource, mode: development && process.argv.includes('--mock') ? 'mock' : 'real' });
    try { await translations.changeLanguage(resolveLanguage((await core.config.get()).ui?.language, systemLocale)); } catch {}
    const coreInitialization=core.initialize();void coreInitialization.catch(()=>{});
    let configuredMusicHome;
    try { const storage=JSON.parse(fs.readFileSync(path.join(localRoot,'music-storage.json'),'utf8'));if(storage.schemaVersion===1&&typeof storage.home==='string'&&path.isAbsolute(storage.home))configuredMusicHome=storage.home; } catch {}
    const requestedMiHome = process.env.DAWLOOP_MI_HOME || configuredMusicHome || path.join(localRoot,'MusicIntelligence');
    // 打包宿主可能重定向用户目录；保留后续严格来源检查的同一真实路径。
    await fs.promises.mkdir(requestedMiHome,{recursive:true});
    const miHome = await fs.promises.realpath(requestedMiHome);
    const miRuntime=await managedRuntime(miHome);
    music=new MusicIntelligenceService({home:miHome,python:miRuntime.python,allowLegacyPitchInstall:false,componentRoot:app.isPackaged?path.join(process.resourcesPath,'components'):'D:/1DAWLoop/RuntimeComponents',localRuntimeRoot:testingOverride?path.join(testingOverride,'offline-resources'):app.isPackaged?path.resolve(process.resourcesPath,'../../..','MusicIntelligence'):'D:/1DAWLoop/MusicIntelligence',fetcher:(url,options)=>net.fetch(url,options)});music.runtimeInfo=miRuntime;desktopInitialization=coreInitialization.then(async()=>{await core.logs.emit('Desktop','INFO',safeStartupRecord('DESKTOP_DEPENDENCY_CHECK',product));await music.initialize();});void desktopInitialization.catch(()=>{});
    protocol.handle("dawloop-audio",request=>music.audioPreview.response(request));
    window = new BrowserWindow({ width: 1180, height: 800, minWidth: 900, minHeight: 620, title: 'DAWLoop Desktop', backgroundColor: '#000000', icon:brandIcon, show: false,
      webPreferences: { preload: path.join(directory, 'preload.cjs'), nodeIntegration: false, contextIsolation: true, sandbox: true } });
    window.setMenuBarVisibility(false);
    window.webContents.on('preload-error', () => console.error('DESKTOP_PRELOAD_FAILED'));
    window.webContents.on('render-process-gone', () => console.error('DESKTOP_RENDERER_GONE'));
    window.webContents.on('console-message', details => { if (details.level === 'error') console.error('DESKTOP_RENDERER_ERROR'); });
    window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
    window.webContents.on('will-navigate', event => event.preventDefault());
    window.webContents.session.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
    ipcMain.handle('dawloop:updates',async(event,method,params)=>{
      if(!trusted(event)||quitting||!['get','check','configure','snooze','open'].includes(method))return failure();
      try{return {apiVersion:1,ok:true,data:await updates.call(method,params)};}catch{return {apiVersion:1,ok:false,error:{code:'UPDATE_REQUEST_FAILED',category:'protocol',message:'UPDATE_REQUEST_FAILED',recoverable:true}};}
    });
    ipcMain.handle('dawloop:call', async (event, method, params) => {
      if (!trusted(event) || !rendererMethodAllowed(method, development)) return failure();
      try { if (JSON.stringify(params ?? null).length > 64 * 1024) return failure(); } catch { return failure(); }
      if (method === 'getDesktopEnvironment') {
        let saved,preferences; try { preferences=(await core.config.get()).ui;saved=preferences?.language; } catch {}
        return { apiVersion:1, ok:true, data:{ reducedMotion:preferences?.reducedMotion===true, systemLocale, language:resolveLanguage(saved, systemLocale), languageExplicit: saved !== undefined, development, ...product } };
      }
      await desktopInitialization;const result = await core.call(method, params);
      if (method === 'getDiagnostics' && result.ok) lastDiagnosticText = JSON.stringify(result.data, null, 2) + '\n';
      if (method === 'updateConfig' && result.ok) {
        await translations.changeLanguage(resolveLanguage(result.data.ui?.language, systemLocale)); updateTray();
        if (process.env.DAWLOOP_DEV_LAUNCH_CHECK === '1') console.log('DESKTOP_LANGUAGE', JSON.stringify({ language:translations.language, tray:[translations.t('native.show'),translations.t('native.quit')] }));
      }
      return result;
    });
    const getStudio=async()=>{await desktopInitialization;if(!studio){studio=new TranscriptionStudio(music);await studio.initialize();}return studio;};
    ipcMain.handle('dawloop:studio',async(event,method,p)=>{
      if(!trusted(event)||quitting)return failure();
      try{
        if(JSON.stringify(p??null).length>4*1024*1024)throw Error('IPC_REJECTED');
        const st=await getStudio();let data;
        if(method==='list')data=await st.list();
        else if(method==='open')data=await st.open(p.id);
        else if(method==='import'){const picked=await dialog.showOpenDialog(window,{properties:['openFile'],filters:[{name:'Audio',extensions:['wav','mp3','flac']}]});data=picked.canceled?null:await st.importAudio(picked.filePaths[0]);}
        else if(method==='drop'){if(!Array.isArray(p?.paths)||p.paths.length!==1||typeof p.paths[0]!=='string')throw Error('IPC_REJECTED');data=await st.importAudio(p.paths[0]);}
        else if(method==='restore'){const picked=await dialog.showOpenDialog(window,{properties:['openDirectory']});data=picked.canceled?null:await st.restore(picked.filePaths[0]);}
        else if(method==='save')data=await st.save(p);
        else if(method==='reset')data=await st.reset(p);
        else if(method==='start')data=st.start(p.id);
        else if(method==='cancel')data=await st.cancel(p.id);
        else if(method==='preview')data=await music.preview(st.get(p.id).assetId);
        else if(method==='reference'){const s=st.get(p.id);if(s.revision!==p.revision||s.state!=='READY')throw Error('STUDIO_REVISION_CHANGED');const picked=await dialog.showSaveDialog(window,{defaultPath:'DAWLoop-reference-r'+s.revision+'.json',filters:[{name:'JSON',extensions:['json']}]});if(!picked.canceled){if(s.rawDirectory&&path.resolve(picked.filePath).startsWith(path.resolve(s.rawDirectory)+path.sep))throw Error('STUDIO_ORIGINAL_PROTECTED');const data={schemaVersion:1,source:'SheetSage2',status:'UNREVIEWED_REFERENCE',timeUnit:'seconds',chords:s.chords,keys:s.keys,structure:s.structure,beats:s.beats,voicing:'RECONSTRUCTED_FROM_LABEL',currentChordNotes:s.tracks.find(t=>t.id==='chords')?.notes??[],notesProvenance:s.edited?'USER_EDITED':'MODEL_LABEL_RECONSTRUCTION',sessionId:s.id,revision:s.revision,modelVersions:s.modelVersions};await fs.promises.writeFile(picked.filePath,JSON.stringify(data,null,2),'utf8');}data=!picked.canceled;}
        else if(method==='saveAs'){const source=st.dragFile(p);const picked=await dialog.showSaveDialog(window,{defaultPath:'Suno_'+p.track+'.mid',filters:[{name:'MIDI',extensions:['mid']}]});if(!picked.canceled){await fs.promises.copyFile(source,picked.filePath);await st.exported(p,'SAVE_AS');}data=!picked.canceled;}
        else throw Error('IPC_REJECTED');
        return {apiVersion:1,ok:true,data};
      }catch(e){return {apiVersion:1,ok:false,error:{code:e.message,category:'music',message:e.message,recoverable:true}};}
    });
    ipcMain.handle('dawloop:studio-drag',(event,p)=>{
      if(!trusted(event)||quitting||!studio)return failure();
      try{const file=studio.dragFile(p);if(!fs.statSync(file).isFile()||fs.readFileSync(file).subarray(0,4).toString()!=='MThd')throw Error('STUDIO_MIDI_REJECTED');event.sender.startDrag({file,icon:nativeImage.createFromPath(brandIcon).resize({width:32,height:32})});void studio.exported(p,'NATIVE_START_REQUESTED');return {apiVersion:1,ok:true,data:{nativeStarted:true}};}catch(e){return {apiVersion:1,ok:false,error:{code:e.message,category:'music',message:e.message,recoverable:true}};}
    });
    const musicMethods=new Set(['styleGenerationAnalysis','styleGenerationWorkspace','styleGenerationCreate','styleGenerationImport','styleGenerationFailure','styleGenerationReject','styleGenerationRate','styleGenerationReveal','styleGenerationPreview','styleGenerationRevise','styleGenerationAnalyze','styleGenerationCancel','styleSemanticStart','styleSemanticStatus','styleSemanticCancel','styleAuditionDisposition','styleAuditionLeaveBlind','styleAuditionSummary','styleAuditionList','styleAuditionReveal','styleAuditionRate','styleAuditionPreview','styleFullPromptSave','styleSong','styleSectionEdit','styleFullPrompt','styleRangePreview','styleRangeSearch','styleOpen','styleSearch','styleFeedback','styleProfile','stylePreview','archivedAssets','savedScores','saveScore','audioSetupStatus','connectLocalAudioRuntime','basicStatus','configureAudioRuntime','saveAsset','dismiss','reviewOffsets','setupStatus','setupFinish','setupInstall','openYueExperience','status','models','jobs','analyze','cancel','install','check','verify','load','unload','modelDiagnostics','abc','profile','removeAsset','collection','preview','releasePreview','waveform','extractEmbedding','transcribe','generate','importAudio','importAbc','importMidi','exportMidi']);
    ipcMain.handle('dawloop:music',async(event,method,params)=>{
      if(!trusted(event)||quitting||!musicMethods.has(method))return failure();
      try { if(JSON.stringify(params??null).length>1024*1024)return failure();
        await desktopInitialization;let data;
        if(method.startsWith('style')){styleLab??=new StyleLabBridge(music);if(method==='styleOpen'){if(params!==undefined)throw Error('IPC_REJECTED');const picked=await dialog.showOpenDialog(window,{properties:['openDirectory']});data=picked.canceled?null:await styleLab.open(picked.filePaths[0]);}else if(method==='styleGenerationImport'){if(!params||Object.keys(params).sort().join()!=='metadata,prompt')throw Error('IPC_REJECTED');const selected=await dialog.showOpenDialog(window,{properties:['openFile'],filters:[{name:'Audio',extensions:['wav','mp3','flac']}]});data=selected.canceled?null:await styleLab.call('generationImport',{...params,path:selected.filePaths[0]});}else if(method==='styleGenerationPreview'){data=await styleLab.generationPreview(params);}else if(method==='styleGenerationAnalyze'||method==='styleGenerationCancel'){data=await styleLab.generation(method,params);}else if(method==='styleSemanticStart'||method==='styleSemanticCancel'||method==='styleSemanticStatus'){data=await styleLab.semantic(method,params);}else if(method==='styleAuditionPreview'){data=await styleLab.preview(null,null,params);}else if(method==='styleRangePreview'){data=await styleLab.preview(null,params);}else if(method==='stylePreview'){if(!params||Object.keys(params).join()!=='id')throw Error('IPC_REJECTED');data=await styleLab.preview(params.id);}else{const operations={styleGenerationAnalysis:'generationAnalysis',styleGenerationWorkspace:'generationWorkspace',styleGenerationCreate:'generationCreate',styleGenerationFailure:'generationFailure',styleGenerationReject:'generationReject',styleGenerationRate:'generationRate',styleGenerationReveal:'generationReveal',styleGenerationRevise:'generationRevise',styleAuditionDisposition:'auditionDisposition',styleAuditionLeaveBlind:'auditionLeaveBlind',styleAuditionSummary:'auditionSummary',styleAuditionList:'auditionList',styleAuditionReveal:'auditionReveal',styleAuditionRate:'auditionRate',styleFullPromptSave:'fullPromptSave',styleSong:'song',styleSectionEdit:'sectionEdit',styleFullPrompt:'fullPrompt',styleRangeSearch:'rangeSearch',styleSearch:'search',styleFeedback:'feedback',styleProfile:'profile'};data=await styleLab.call(operations[method],params);}}else if(method==='openYueExperience'){await shell.openExternal('https://yue.noizai.net/');data=true;}else if(method==='importAudio'||method==='importMidi'||method==='importAbc'){
          const selected=await dialog.showOpenDialog(window,{properties:['openFile'],filters:[{name:method==='importAudio'?'Audio':method==='importAbc'?'ABC':'MIDI',extensions:method==='importAudio'?['wav','mp3','flac']:method==='importAbc'?['abc']:['mid','midi']}]});
          data=selected.canceled?null:method==='importAudio'?await music.importAudio(selected.filePaths[0]):method==='importAbc'?await music.importAbc(selected.filePaths[0]):await music.importMidi(selected.filePaths[0]);
        }else if(method==='exportMidi'){const selected=await dialog.showSaveDialog(window,{defaultPath:'DAWLoop-score.mid',filters:[{name:'MIDI',extensions:['mid']}]});data=selected.canceled?null:await music.exportMidi(params.score,selected.filePath);}
        else if(method==='modelDiagnostics'){const selected=await dialog.showSaveDialog(window,{defaultPath:'DAWLoop-model-diagnostics.json',filters:[{name:'JSON',extensions:['json']}]});if(selected.canceled)data=null;else{const report=JSON.stringify(await music.diagnostics(),null,2);if(Buffer.byteLength(report)>256*1024)throw Error('MI_DIAGNOSTICS_TOO_LARGE');await fs.promises.writeFile(selected.filePath,report,'utf8');data=true;}}
        else if(method==='configureAudioRuntime'){if(params!==undefined&&Object.keys(params).length)throw Error('IPC_REJECTED');const selected=await dialog.showOpenDialog(window,{properties:['openDirectory']});data=selected.canceled?null:await music.configureAudioRuntime(selected.filePaths[0]);}
        else data=await music.call(method,params??{});
        return {apiVersion:1,ok:true,data};
      } catch(error){const code=/^[A-Z0-9_]+$/.test(error.message)?error.message:'MI_TASK_FAILED';return {apiVersion:1,ok:false,error:{code,message:code,category:'music',recoverable:true}};}
    });
    ipcMain.handle('dawloop:copy', async (event, text) => {
      if (!trusted(event) || typeof text !== 'string' || text.length > 1024 * 1024) return failure();
      try { await clipboard.writeText(text); return { apiVersion: 1, ok: true, data: null }; }
      catch { return failure(); }
    });
    ipcMain.handle('dawloop:browse-host', async event => {
      if (!trusted(event)) return failure();
      try {
        const result = await dialog.showOpenDialog(window, { title:translations.t('native.browseTitle'), properties:['openFile'], filters:[{ name:'FL Studio', extensions:['exe'] }] });
        return { apiVersion: 1, ok: true, data: result.canceled ? null : result.filePaths[0] };
      } catch { return failure(); }
    });
    ipcMain.handle('dawloop:export-diagnostics', async (event, ...args) => {
      if (!trusted(event) || args.length || exporting || quitting) return failure();
      exporting = true;
      try {
        return await exportDiagnosticReport({ reportText:lastDiagnosticText,
          chooseFile:() => dialog.showSaveDialog(window, { title:translations.t('native.exportTitle'), defaultPath:'DAWLoop-diagnostics.json', filters:[{ name:'JSON', extensions:['json'] }] }),
          writeFile:fs.promises.writeFile });
      } finally { exporting = false; }
    });
    tray = new Tray(nativeImage.createFromPath(brandIcon));
    tray.setToolTip('DAWLoop Desktop'); updateTray();
    tray.on('double-click', () => window.show());
    await window.loadFile(path.resolve(directory, '../dist/index.html'));
    // 更新检查与音乐工作区初始化解耦，网络不可用不会阻止窗口打开。
    void updates.check().catch(()=>{});
    updateTimer=setInterval(()=>void updates.check().catch(()=>{}),30*60*1000);
    updateTimer.unref();
    if (!process.argv.includes('--smoke')) { window.show(); window.focus(); }
    if (process.env.DAWLOOP_DEV_LAUNCH_CHECK === '1') console.log('DESKTOP_RENDERER_READY', JSON.stringify({ visible:window.isVisible(), language:translations.language, systemLocale }));
    await desktopInitialization;
    // 配置和界面初始化成功后才启动受控 worker，避免壳层失败遗留宿主。
    if(sessionSpec && !quitting) {
      sessionStartup=startTrustedSessionWorker(sessionSpec,{cancelled:()=>quitting});
      sessionWorker=await sessionStartup;
      if(sessionInvalidation)sessionUnsubscribe=sessionWorker.source.onInvalidation(sessionInvalidation);
      if(quitting)await sessionWorker.close();
    }
  }).catch(error => { console.error('DESKTOP_STARTUP_FAILED', /^[A-Z0-9_]{1,120}$/.test(error?.message) ? error.message : 'STARTUP_UNAVAILABLE'); if(!quitting)app.exit(1); });
  app.on('window-all-closed', () => app.quit());
  app.on('before-quit', event => {
    clearInterval(updateTimer);styleLab?.close();
    if (quitting || !core) return;
    event.preventDefault(); quitting = true;
    Promise.resolve(desktopInitialization).catch(()=>{}).then(()=>studio?.close()).then(()=>music?.close()).then(()=>core.close()).then(()=>sessionStartup?.catch(()=>undefined)).then(()=>sessionWorker?.close()).finally(() => { tray?.destroy(); app.quit(); });
  });
}
