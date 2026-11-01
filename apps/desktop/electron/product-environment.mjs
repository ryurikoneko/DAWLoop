import fs from 'node:fs';
import path from 'node:path';

export function controllerDependency(documents, appData) {
  if(!documents || !appData)return 'not-probed';
  let settings=path.join(documents,'Image-Line/FL Studio/Settings');
  try {
    const saved=path.join(appData,'DAWLoop/config.json');
    if(fs.existsSync(saved)) {
      if(fs.statSync(saved).size>65536)return 'unavailable';
      const configured=JSON.parse(fs.readFileSync(saved,'utf8')).fl_settings_dir;
      if(configured!==undefined) {
        if(typeof configured!=='string' || !path.isAbsolute(configured))return 'unavailable';
        settings=configured;
      }
    }
    // 安装文件存在只说明本机材料可见，不能证明已加载或来源受信。
    const directory=path.join(settings,'Hardware/DAWLoopMCP');
    for(const name of ['device_DAWLoopController.py','upstream_backend.py']) {
      try {if(!fs.statSync(path.join(directory,name)).isFile())return 'not-found';}
      catch(error){return error.code==='ENOENT'?'not-found':'unavailable';}
    }
    return 'present-unverified';
  } catch {return 'unavailable';}
}
export function productEnvironment({ isPackaged, root, version, electronVersion, nodeVersion, documents, appData, releaseChannel }) {
  return { packaged:isPackaged, appVersion:version, electronVersion, nodeVersion,
    releaseChannel:isPackaged ? !/internal/i.test(version)&&['stable','preview'].includes(releaseChannel)?releaseChannel:'internal' : 'development',
    dependencies:{ core:fs.existsSync(path.join(root,'packages/app-core/index.mjs')) ? 'desktop-only' : 'unavailable',
      python:isPackaged ? 'not-bundled' : 'development-external', controller:controllerDependency(documents,appData), host:'user-installed' } };
}
export function observerPython(isPackaged, resourcesPath, environment) {
  // 普通用户候选不信任 PATH 或开发环境变量，也不借用 Session A 的冻结解释器。
  return isPackaged ? path.join(resourcesPath,'python-not-bundled','python.exe') : environment.DAWLOOP_PYTHON || 'python';
}
export function safeStartupRecord(code, product) {
  return JSON.stringify({ code, appVersion:product.appVersion, channel:product.releaseChannel,
    electronVersion:product.electronVersion, nodeVersion:product.nodeVersion, dependencies:product.dependencies });
}
