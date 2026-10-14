import fs from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { supportedLanguages } from './language.mjs';

export class AppError extends Error {
  constructor(code, category = 'configuration') { super(code); this.code = code; this.category = category; }
}
export const defaults = () => ({ schemaVersion: 1, activeProfileId: 'default',
  general: { launchAtLogin: false, detectHostOnStartup: true, autoStartRuntime: false, logLevel: 'Normal' },
  host: { executablePath: '' }, ui: { mode: 'USER_MODE' },
  features: { experimentalMixerWrite: false, pluginParameterEditing: false, nativeGopherTransport: false } });
export const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
export function validateKeys(value) {
  if (object(value)) for (const [key, item] of Object.entries(value)) {
    if (['__proto__', 'constructor', 'prototype'].includes(key)) throw new AppError('INVALID_FIELD');
    validateKeys(item);
  }
  else if (Array.isArray(value)) value.forEach(validateKeys);
}
export function merge(base, patch) {
  validateKeys(patch);
  if (!object(patch)) throw new AppError('INVALID_CONFIG');
  const next = structuredClone(base);
  for (const [key, value] of Object.entries(patch)) next[key] = object(value) && object(next[key]) ? merge(next[key], value) : structuredClone(value);
  return next;
}
export async function atomicWrite(filename, value) {
  await fs.mkdir(path.dirname(filename), { recursive: true });
  const temporary = `${filename}.${randomUUID()}.tmp`;
  try {
    const handle = await fs.open(temporary, 'wx', 0o600);
    try { await handle.writeFile(JSON.stringify(value, null, 2) + '\n', 'utf8'); await handle.sync(); }
    finally { await handle.close(); }
    await fs.rename(temporary, filename);
  } finally { await fs.rm(temporary, { force: true }); }
}
export async function readVersioned(filename, fallback, validate) {
  let text;
  try { text = await fs.readFile(filename, 'utf8'); }
  catch (error) { if (error.code !== 'ENOENT') throw error; const value = fallback(); validate(value); await atomicWrite(filename, value); return value; }
  let value;
  try { value = JSON.parse(text); } catch { throw new AppError('INVALID_JSON'); }
  if (!object(value)) throw new AppError('INVALID_CONFIG');
  validateKeys(value);
  const migrating = value.schemaVersion === 0;
  if (migrating) value = merge(fallback(), { ...value, schemaVersion: 1 });
  validate(value);
  if (migrating) {
    // 先保留升级前原字节；备份失败时不写新版本。
    await fs.copyFile(filename, `${filename}.v0.${randomUUID()}.bak`, fs.constants.COPYFILE_EXCL);
    await atomicWrite(filename, value);
  }
  return value;
}
export function validateConfig(value) {
  if (value.ui?.reducedMotion !== undefined && typeof value.ui.reducedMotion !== 'boolean') throw new AppError('INVALID_CONFIG');
  if (value.ui?.mode !== undefined && !['USER_MODE', 'DEVELOPER_MODE'].includes(value.ui.mode)) throw new AppError('INVALID_CONFIG');
  if (value.ui?.onboardingCompleted !== undefined && typeof value.ui.onboardingCompleted !== 'boolean') throw new AppError('INVALID_CONFIG');
  if (value.ui !== undefined && (!object(value.ui) || (value.ui.language !== undefined && !supportedLanguages.includes(value.ui.language)))) throw new AppError('INVALID_LANGUAGE');
  if (value.schemaVersion !== 1) throw new AppError('UNSUPPORTED_SCHEMA');
  if (typeof value.activeProfileId !== 'string' || !/^[a-z0-9-]{1,64}$/.test(value.activeProfileId)) throw new AppError('INVALID_CONFIG');
  for (const key of ['general', 'host', 'features']) if (!object(value[key])) throw new AppError('INVALID_CONFIG');
  for (const key of ['launchAtLogin', 'detectHostOnStartup', 'autoStartRuntime']) if (typeof value.general[key] !== 'boolean') throw new AppError('INVALID_CONFIG');
  if (!['Normal', 'Detailed', 'Debug'].includes(value.general.logLevel) || typeof value.host.executablePath !== 'string' || value.host.executablePath.length > 4096) throw new AppError('INVALID_CONFIG');
  for (const key of Object.keys(defaults().features)) if (typeof value.features[key] !== 'boolean') throw new AppError('INVALID_CONFIG');
  validateKeys(value);
}
export class ConfigService {
  constructor(root) { this.filename = path.join(root, 'config', 'desktop.json'); }
  get() { return readVersioned(this.filename, defaults, validateConfig); }
  async update(patch) { const value = merge(await this.get(), patch); validateConfig(value); await atomicWrite(this.filename, value); return value; }
}
