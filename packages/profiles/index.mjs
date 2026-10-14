import fs from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { AppError, atomicWrite, merge, object, readVersioned, validateKeys } from '../config/index.mjs';

export const profileDefaults = (id = 'default', name = 'Default') => ({ schemaVersion: 1, id, name, runtime: {}, verification: { preset: 'Strict' }, agent: {}, mixer: {}, ui: {} });
export function validateProfile(value) {
  if (value.schemaVersion !== 1) throw new AppError('UNSUPPORTED_SCHEMA');
  if (typeof value.id !== 'string' || !/^[a-z0-9-]{1,64}$/.test(value.id) || typeof value.name !== 'string' || !value.name.trim() || value.name.length > 120) throw new AppError('INVALID_PROFILE');
  for (const key of ['runtime', 'verification', 'agent', 'mixer', 'ui']) if (!object(value[key])) throw new AppError('INVALID_PROFILE');
  if (value.verification.preset !== undefined && !['Strict', 'Balanced', 'Fast', 'Custom'].includes(value.verification.preset)) throw new AppError('INVALID_PROFILE');
  validateKeys(value);
}
export class ProfileService {
  constructor(root) { this.root = path.join(root, 'profiles'); }
  filename(id) { if (typeof id !== 'string' || !/^[a-z0-9-]{1,64}$/.test(id)) throw new AppError('INVALID_PROFILE_ID'); return path.join(this.root, `${id}.json`); }
  async get(id) {
    const file = this.filename(id);
    if (id !== 'default') { try { await fs.access(file); } catch { throw new AppError('PROFILE_NOT_FOUND'); } }
    const value = await readVersioned(file, () => profileDefaults(id), candidate => {
      validateProfile(candidate);
      if (candidate.id !== id) throw new AppError('PROFILE_ID_MISMATCH');
    });
    if (value.id !== id) throw new AppError('PROFILE_ID_MISMATCH');
    return value;
  }
  async list() { await this.get('default'); const names = await fs.readdir(this.root); return Promise.all(names.filter(x => /^[a-z0-9-]+\.json$/.test(x)).sort().map(x => this.get(x.slice(0, -5)))); }
  async create(name) { const value = profileDefaults(randomUUID(), name); validateProfile(value); await atomicWrite(this.filename(value.id), value); return value; }
  async update(value) { validateProfile(value); const next = merge(await this.get(value.id), value); validateProfile(next); await atomicWrite(this.filename(value.id), next); return next; }
}
