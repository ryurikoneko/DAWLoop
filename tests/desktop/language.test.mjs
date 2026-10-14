import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { resolveLanguage } from '../../packages/config/language.mjs';
import { ConfigService, defaults, atomicWrite } from '../../packages/config/index.mjs';
import { nativeTranslations } from '../../apps/desktop/electron/native-i18n.mjs';
import { AppCore } from '../../packages/app-core/index.mjs';

test('语言优先级：显式选择覆盖系统，中文仅映射大陆与新加坡', () => {
  for (const locale of ['zh-CN','zh-SG','zh_cn','ZH-sg']) assert.equal(resolveLanguage(undefined, locale), 'zh-CN');
  for (const locale of ['zh-TW','zh-HK','zh','en-US','ja-JP','fr-FR','']) assert.equal(resolveLanguage(undefined, locale), 'en-US');
  assert.equal(resolveLanguage('en-US','zh-CN'),'en-US');
  assert.equal(resolveLanguage('zh-CN','en-US'),'zh-CN');
});
test('双向重启持久化，旧配置兼容，未知 ui 字段保留，坏值不覆盖', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(),'dawloop-language-'));
  t.after(() => fs.rm(root,{recursive:true,force:true}));
  const service = new ConfigService(root);
  const old = defaults(); delete old.ui; await atomicWrite(service.filename, old);
  assert.equal((await service.get()).ui,undefined);
  await service.update({ui:{language:'en-US',future:{x:1}}});
  assert.equal((await new ConfigService(root).get()).ui.language,'en-US');
  await service.update({ui:{language:'zh-CN'}});
  assert.deepEqual((await new ConfigService(root).get()).ui,{language:'zh-CN',future:{x:1}});
  const before = await fs.readFile(service.filename,'utf8');
  await assert.rejects(service.update({ui:{language:'zh-TW'}}),e=>e.code==='INVALID_LANGUAGE');
  assert.equal(await fs.readFile(service.filename,'utf8'),before);
});
test('原生托盘与对话框复用资源并立即切换', async () => {
  const i18n = nativeTranslations('zh-CN');
  assert.equal(i18n.t('native.quit'),'退出');
  await i18n.changeLanguage('en-US');
  assert.equal(i18n.t('native.quit'),'Quit');
  assert.equal(i18n.t('native.browseTitle'),'Select FL64.exe');
});
test('原生文案同样禁止跨语言回退，开发模式显示缺键', () => {
  const production=nativeTranslations('en-US');
  production.removeResourceBundle('en-US','common');
  assert.equal(production.t('native.quit'),'Text unavailable');
  const development=nativeTranslations('zh-CN',true);
  assert.equal(development.t('missingNativeKey'),'[missing:missingNativeKey]');
});
test('语言修改不改变协议状态、能力、机器错误码及宿主写权限', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(),'dawloop-contract-language-'));
  const core = new AppCore({roamingRoot:root,localRoot:root,development:true, mode:'mock'});
  await core.initialize(); t.after(async()=>{await core.close();await fs.rm(root,{recursive:true,force:true});});
  const before = (await core.call('getAppStatus')).data;
  await core.call('updateConfig',{ui:{language:'zh-CN'}});
  const after = (await core.call('getAppStatus')).data;
  for (const key of ['runtime','host','bridges','capabilities','backend','label']) assert.deepEqual(before[key],after[key]);
  const error = (await core.call('plugin.parameter.write',{value:1})).error;
  assert.equal(error.code,'METHOD_UNAVAILABLE');assert.equal(error.message,error.code);
});
