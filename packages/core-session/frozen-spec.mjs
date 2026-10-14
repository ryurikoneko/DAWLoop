import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';

const hash = value => createHash('sha256').update(value).digest('hex');
const require = (value, code) => { if (!value) throw Object.assign(new Error(code), { code }); };

export async function verifyFrozenSessionSource(spec, config) {
  const source = config.source;
  if (!source?.frozen_execution) return null;
  const root = await fs.realpath(source.checkpoint_repository);
  const raw = await fs.readFile(path.join(root, 'source_manifest.json'));
  const digest = hash(raw);
  require(digest === source.frozen_execution.manifest_sha256 && path.basename(root) === `sha256-${digest}`, 'FROZEN_MANIFEST_REJECTED');
  const manifest = JSON.parse(raw.toString('utf8'));
  require(manifest.schema_version === 2 && manifest.allowed_operations.includes(config.test_operation), 'FROZEN_OPERATION_REJECTED');
  require(source.repository_root === path.join(root, 'public') && source.package_root === path.join(root, 'public', 'src')
    && source.private_root === path.join(root, 'private'), 'FROZEN_ROOT_REJECTED');
  require(await fs.realpath(spec.python) === path.join(root, 'runtime', 'python.exe')
    && await fs.realpath(spec.launcherPath) === path.join(root, 'private', 'dawloop_automix_live_session.py'), 'FROZEN_ENTRY_REJECTED');
  const evidence = [];
  for (const row of manifest.source_sha256s) {
    require(['EXECUTION_DEPENDENCY', 'PROTECTED_ENVIRONMENT', 'CONTRACT_DOCUMENT', 'EVIDENCE_DOCUMENT'].includes(row.category), 'FROZEN_CATEGORY_REJECTED');
    let file;
    if (row.category === 'PROTECTED_ENVIRONMENT') {
      require(row.snapshot.startsWith('protected/') && ['fixture', 'descriptor', 'host', 'installed_controller'].includes(row.reason), 'PROTECTED_CATEGORY_REJECTED');
      file = row.path;
    } else {
      require(!path.isAbsolute(row.snapshot) && !row.snapshot.split(/[\\/]/).includes('..'), 'FROZEN_PATH_REJECTED');
      file = await fs.realpath(path.join(root, row.snapshot));
      require(file.startsWith(root + path.sep), 'FROZEN_PATH_REJECTED');
      const prefix = row.snapshot.split('/')[0];
      require(row.category !== 'EVIDENCE_DOCUMENT' || prefix === 'evidence', 'FROZEN_CATEGORY_REJECTED');
      require(row.category !== 'CONTRACT_DOCUMENT' || prefix === 'contracts', 'FROZEN_CATEGORY_REJECTED');
      require(row.category !== 'EXECUTION_DEPENDENCY' || ['public', 'private', 'vendor', 'runtime'].includes(prefix), 'FROZEN_CATEGORY_REJECTED');
    }
    const matches = hash(await fs.readFile(file)) === row.sha256;
    if (row.category === 'EVIDENCE_DOCUMENT') { evidence.push({ path: file, matches }); continue; }
    require(matches, 'FROZEN_DEPENDENCY_CHANGED');
    if (row.category !== 'PROTECTED_ENVIRONMENT') {
      // 解释器启动前校验封存状态；worker 随后持有禁止写入和删除的原生文件租约。
      require(((await fs.stat(file)).mode & 0o222) === 0, 'FROZEN_SOURCE_NOT_SEALED');
    }
  }
  require(((await fs.stat(path.join(root, 'source_manifest.json'))).mode & 0o222) === 0, 'FROZEN_MANIFEST_NOT_SEALED');
  return { bundleId: path.basename(root), manifestSha256: digest, evidence };
}
