export const supportedLanguages = ['zh-CN', 'en-US'];
export function resolveLanguage(explicit, systemLocale = '') {
  if (supportedLanguages.includes(explicit)) return explicit;
  const normalized = String(systemLocale).replaceAll('_', '-').toLowerCase();
  return ['zh-cn', 'zh-sg'].includes(normalized) ? 'zh-CN' : 'en-US';
}
