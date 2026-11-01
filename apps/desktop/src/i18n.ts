import i18next, { type i18n as I18n } from 'i18next';
import { initReactI18next } from 'react-i18next';
import type { Language } from '../../../packages/shared-types/contracts';

const files = import.meta.glob('../locales/*/*.json', { eager: true, import: 'default' });
export const resources: Record<string, Record<string, object>> = {};
for (const [filename, values] of Object.entries(files)) {
  const match = filename.match(/locales\/([^/]+)\/([^/]+)\.json$/)!;
  (resources[match[1]] ??= {})[match[2]] = values as object;
}
export function createDesktopI18n(language: Language = 'en-US', data = resources, development = false): I18n {
  const instance = i18next.createInstance();
  void instance.use(initReactI18next).init({
    resources: data, lng: language, supportedLngs: ['zh-CN', 'en-US'], load: 'currentOnly',
    ns: Object.keys(data['en-US'] ?? {}), defaultNS: 'common',
    fallbackLng: false,
    returnEmptyString: false, returnNull: false, initAsync: false,
    interpolation: { escapeValue: false }, react: { useSuspense: false },
    parseMissingKeyHandler: (key, defaultValue) => development ? `[missing:${key}]` : defaultValue ?? (instance.language === 'zh-CN' ? '内容暂不可用，请重试或查看诊断。' : 'Content is temporarily unavailable. Retry or check diagnostics.'),
  });
  return instance;
}
