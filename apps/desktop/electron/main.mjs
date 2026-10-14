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
import { windowsNotifier } from './update-toast.mjs';
protocol.registerSchemesAsPrivileged([{scheme:"dawloop-audio",privileges:{standard:true,secure:true,stream:true,corsEnabled:true}}]);
if(process.platform==='win32')app.setAppUserModelId('DAWLoop.Desktop.Internal');
const development = desktopDevelopment(app.isPackaged, process.argv);

const directory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(directory, '../../..');
let packagedChannel;
try {packagedChannel=JSON.parse(fs.readFileSync(path.join(app.getAppPath(),'package.json'),'utf8')).dawloopReleaseChannel;}catch{}
const product = productEnvironment({ isPackaged:app.isPackaged, root, version:app.getVersion(), releaseChannel:packagedChannel, electronVersion:process.versions.electron, nodeVersion:process.versions.node, documents:app.getPath('documents'), appData:app.getPath('appData') });
const override = process.env.DAWLOOP_DESKTOP_DATA_ROOT;
if (override) {
  const browserData = path.join(override, 'electron');
  fs.mkdirSync(browserData, { recursive:true });
  app.setPath('userData', browserData);
}
let music;let desktopInitialization;let updates;
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
    const miHome = process.env.DAWLOOP_MI_HOME || configuredMusicHome || path.join(localRoot,'MusicIntelligence');
    const miRuntime=await managedRuntime(miHome);
    music=new MusicIntelligenceService({home:miHome,python:miRuntime.python,allowLegacyPitchInstall:!app.isPackaged,componentRoot:app.isPackaged?path.join(process.resourcesPath,'components'):'D:/1DAWLoop/RuntimeComponents',localRuntimeRoot:override?path.join(override,'offline-resources'):app.isPackaged?path.resolve(process.resourcesPath,'../../..','MusicIntelligence'):'D:/1DAWLoop/MusicIntelligence',fetcher:(url,options)=>net.fetch(url,options)});music.runtimeInfo=miRuntime;desktopInitialization=coreInitialization.then(async()=>{await core.logs.emit('Desktop','INFO',safeStartupRecord('DESKTOP_DEPENDENCY_CHECK',product));await music.initialize();});void desktopInitialization.catch(()=>{});
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
    const musicMethods=new Set(['archivedAssets','savedScores','saveScore','audioSetupStatus','connectLocalAudioRuntime','basicStatus','configureAudioRuntime','saveAsset','dismiss','reviewOffsets','setupStatus','setupFinish','setupInstall','openYueExperience','status','models','jobs','analyze','cancel','install','check','verify','load','unload','modelDiagnostics','abc','profile','removeAsset','collection','preview','releasePreview','waveform','extractEmbedding','transcribe','generate','importAudio','importAbc','importMidi','exportMidi']);
    ipcMain.handle('dawloop:music',async(event,method,params)=>{
      if(!trusted(event)||quitting||!musicMethods.has(method))return failure();
      try { if(JSON.stringify(params??null).length>1024*1024)return failure();
        await desktopInitialization;let data;
        if(method==='openYueExperience'){await shell.openExternal('https://yue.noizai.net/');data=true;}else if(method==='importAudio'||method==='importMidi'||method==='importAbc'){
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
    if (quitting || !core) return;
    event.preventDefault(); quitting = true;
    Promise.resolve(desktopInitialization).catch(()=>{}).then(()=>music?.close()).then(()=>core.close()).then(()=>sessionStartup?.catch(()=>undefined)).then(()=>sessionWorker?.close()).finally(() => { tray?.destroy(); app.quit(); });
  });
}
