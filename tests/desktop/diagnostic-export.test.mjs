import test from 'node:test';
import assert from 'node:assert/strict';
import { exportDiagnosticReport } from '../../apps/desktop/electron/diagnostic-export.mjs';

test('只导出缓存字节，取消不写入，缺报告不打开对话框', async () => {
  const writes = []; let choices = 0;
  const chooseFile = async () => { choices++; return { canceled:true }; };
  const writeFile = async (...args) => writes.push(args);
  assert.equal((await exportDiagnosticReport({ chooseFile, writeFile })).error.code, 'DIAGNOSTIC_REPORT_REQUIRED');
  assert.equal(choices, 0);
  assert.equal((await exportDiagnosticReport({ reportText:'{}\n', chooseFile, writeFile })).data.saved, false);
  assert.deepEqual(writes, []);
  const reportText = '{"app":{"backend":"real"}}\n';
  assert.equal((await exportDiagnosticReport({ reportText, chooseFile:async () => ({ canceled:false, filePath:'chosen.json' }), writeFile })).data.saved, true);
  assert.deepEqual(writes, [['chosen.json', reportText, 'utf8']]);
});
test('大小限制按 UTF-8 字节计算；对话框、缺路径、文件系统异常可恢复', async () => {
  let wrote = false; const writeFile = async () => { wrote = true; throw Error('private/path'); };
  const chooseFile = async () => ({ canceled:false, filePath:'chosen.json' });
  assert.equal((await exportDiagnosticReport({ reportText:'中'.repeat(400000), chooseFile, writeFile })).error.code, 'DIAGNOSTIC_REPORT_REQUIRED');
  assert.equal(wrote, false);
  for (const choose of [chooseFile, async () => ({ canceled:false }), async () => { throw Error('secret'); }]) {
    const result = await exportDiagnosticReport({ reportText:'{}', chooseFile:choose, writeFile });
    assert.equal(result.error.code, 'DIAGNOSTIC_EXPORT_FAILED');
    assert.ok(!JSON.stringify(result).includes('private/path'));
    assert.ok(!JSON.stringify(result).includes('secret'));
  }
});
