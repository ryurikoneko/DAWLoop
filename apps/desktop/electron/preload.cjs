const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('dawloop', Object.freeze({
  updates: Object.freeze(Object.fromEntries(['get','check','configure','snooze','open'].map(method=>[method,params=>ipcRenderer.invoke('dawloop:updates',method,params)]))),
  music: Object.freeze(Object.fromEntries(['archivedAssets','savedScores','saveScore','audioSetupStatus','connectLocalAudioRuntime','basicStatus','configureAudioRuntime','saveAsset','dismiss','reviewOffsets','setupStatus','setupFinish','setupInstall','openYueExperience','status','models','jobs','analyze','cancel','install','check','verify','load','unload','modelDiagnostics','abc','profile','removeAsset','collection','preview','releasePreview','waveform','extractEmbedding','transcribe','generate','importAudio','importAbc','importMidi','exportMidi'].map(method=>[method,params=>ipcRenderer.invoke('dawloop:music',method,params)]))),
  call: (method, params) => ipcRenderer.invoke('dawloop:call', method, params),
  copy: text => ipcRenderer.invoke('dawloop:copy', text),
  browseHost: () => ipcRenderer.invoke('dawloop:browse-host'),
  exportDiagnostics: () => ipcRenderer.invoke('dawloop:export-diagnostics')
}));
