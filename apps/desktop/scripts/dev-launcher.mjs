import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';

const directory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(directory, 'package.json'));
const env = { ...process.env };
// Electron 继承此变量时会成为 Node 进程，无法创建窗口。
delete env.ELECTRON_RUN_AS_NODE;
function run(executable, args, windowsHide = true) {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, { cwd: directory, env, stdio: 'inherit', windowsHide });
    child.once('error', reject);
    child.once('exit', (code, signal) => code === 0 ? resolve() : reject(new Error(`${path.basename(executable)} exited: ${code ?? signal}`)));
  });
}
try {
  const [major, minor] = process.versions.node.split('.').map(Number);
  if (major < 22 || (major === 22 && minor < 12)) throw new Error('Node.js 22.12 or newer is required.');
  let ready = false;
  // require('electron') 会触发同步下载；先显式准备二进制以保留失败反馈。
  try { require.resolve('electron'); require.resolve('vite'); require.resolve('typescript'); require.resolve('react-i18next'); ready = true; }
  catch { ready = false; }
  if (!ready) {
    console.log('[DAWLoop] Installing developer dependencies from package-lock.json…');
    if (process.platform === 'win32') await run(process.env.ComSpec || 'cmd.exe', ['/d', '/s', '/c', 'npm.cmd ci --no-audit --no-fund']);
    else await run('npm', ['ci', '--no-audit', '--no-fund']);
  }
  const electronDirectory = path.dirname(require.resolve('electron'));
  const pathFile = path.join(electronDirectory, 'path.txt');
  if (!fs.existsSync(pathFile) || !fs.existsSync(path.join(electronDirectory, 'dist', fs.readFileSync(pathFile, 'utf8').trim()))) {
    console.log('[DAWLoop] Downloading the Electron developer runtime…');
    await run(process.execPath, [path.join(electronDirectory, 'install.js')]);
  }
  console.log('[DAWLoop] Checking TypeScript and building the renderer…');
  await run(process.execPath, [require.resolve('typescript/bin/tsc'), '--noEmit']);
  await run(process.execPath, [path.join(directory, 'node_modules/vite/bin/vite.js'), 'build']);
  console.log('[DAWLoop] Starting Electron…');
  await run(require('electron'), [directory, ...process.argv.slice(2)], false);
} catch (error) {
  console.error(`[DAWLoop] ${error.message}`);
  console.error('[DAWLoop] Check Node.js/npm, dependency download access and the build errors above. No system configuration was changed.');
  process.exitCode = 1;
}
