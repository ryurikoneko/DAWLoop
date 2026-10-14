import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { productEnvironment,observerPython,safeStartupRecord,controllerDependency } from '../../apps/desktop/electron/product-environment.mjs';
import { validateConfig,defaults } from '../../packages/config/index.mjs';

test('普通用户候选不借用开发Python，依赖不可用不冒充会话连接',()=>{
  const product=productEnvironment({isPackaged:true,root:'missing',version:'0.1.0-internal.1',electronVersion:'44.6.0',nodeVersion:'included'});
  assert.equal(product.dependencies.python,'not-bundled');assert.equal(product.dependencies.core,'unavailable');
  assert.equal(product.dependencies.controller,'not-probed');
  assert.ok(observerPython(true,'fixed-resources',{DAWLOOP_PYTHON:'injected'}).includes('python-not-bundled'));
  assert.equal(observerPython(false,'fixed-resources',{DAWLOOP_PYTHON:'developer-python'}),'developer-python');
  assert.equal(product.releaseChannel,'internal');
  const safe=safeStartupRecord('DESKTOP_DEPENDENCY_CHECK',product);
  assert.ok(!safe.includes('missing'));assert.ok(!safe.includes('injected'));
});
test('首次启动偏好只接受布尔，未来未知偏好仍保留',()=>{
  for(const onboardingCompleted of [true,false])validateConfig({...defaults(),ui:{onboardingCompleted,futurePreference:1}});
  assert.throws(()=>validateConfig({...defaults(),ui:{onboardingCompleted:'true'}}));
});
test('公共构建渠道必须来自包元数据；Internal和开发构建不能自升',()=>{
  const base={isPackaged:true,root:'missing',version:'0.6.0',electronVersion:'44.6.0',nodeVersion:'included'};
  assert.equal(productEnvironment({...base,releaseChannel:'stable'}).releaseChannel,'stable');
  assert.equal(productEnvironment({...base,releaseChannel:'preview'}).releaseChannel,'preview');
  assert.equal(productEnvironment({...base,releaseChannel:'unknown'}).releaseChannel,'internal');
  assert.equal(productEnvironment({...base,version:'0.5.6-internal.1',releaseChannel:'stable'}).releaseChannel,'internal');
  assert.equal(productEnvironment({...base,isPackaged:false,releaseChannel:'stable'}).releaseChannel,'development');
});
test('Controller 文件存在不证明加载，错误设置和缺文件明确区分',async t=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'desktop-dependencies-'));t.after(()=>fs.rm(root,{recursive:true,force:true}));
  const documents=path.join(root,'documents'),appData=path.join(root,'roaming');
  assert.equal(controllerDependency(documents,appData),'not-found');
  const hardware=path.join(documents,'Image-Line/FL Studio/Settings/Hardware/DAWLoopMCP');await fs.mkdir(hardware,{recursive:true});
  await fs.writeFile(path.join(hardware,'device_DAWLoopController.py'),'not-loaded');await fs.writeFile(path.join(hardware,'upstream_backend.py'),'not-loaded');
  assert.equal(controllerDependency(documents,appData),'present-unverified');
  await fs.mkdir(path.join(appData,'DAWLoop'),{recursive:true});await fs.writeFile(path.join(appData,'DAWLoop/config.json'),'{invalid');
  assert.equal(controllerDependency(documents,appData),'unavailable');
});
