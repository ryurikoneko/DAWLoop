import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import i18next from 'i18next';

const locales = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../locales');
const manifest = JSON.parse(fs.readFileSync(path.join(locales, 'manifest.json'), 'utf8'));
const resources = Object.fromEntries(manifest.languages.map(language => [language,
  Object.fromEntries(manifest.namespaces.map(namespace => [namespace,
    JSON.parse(fs.readFileSync(path.join(locales, language, namespace + '.json'), 'utf8'))]))]));
export function nativeTranslations(language, development = false) {
  const instance = i18next.createInstance();
  instance.init({ resources, lng:language, supportedLngs:manifest.languages, defaultNS:'common', initAsync:false,
    fallbackLng:false, load:'currentOnly', parseMissingKeyHandler:(key, defaultValue)=>development ? `[missing:${key}]` : defaultValue ?? 'Text unavailable', returnNull:false, returnEmptyString:false });
  return instance;
}
