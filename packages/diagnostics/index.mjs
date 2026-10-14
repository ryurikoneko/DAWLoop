const sensitiveKey = /token|password|secret|api.?key|user.?name|project|path|directory|content/i;
export function redact(value) {
  if (typeof value === 'string') return value
    .replace(/(?:Bearer\s+)[\w.+/=-]+/gi, '[REDACTED]')
    .replace(/(?:token|password|secret|api[_-]?key)\s*[:=]\s*[^\s,;]+/gi, '[REDACTED]')
    .replace(/\b[A-Z]:[\\/][^\r\n"<>]*/gi, '[REDACTED_PATH]')
    .replace(/(?:\/Users\/|\/home\/|\\\\)[^\s"<>]*/g, '[REDACTED_PATH]');
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, sensitiveKey.test(key) ? '[REDACTED]' : redact(item)]));
  return value;
}
export function diagnosticReport(status, config, world = null) {
  // 报告仅导出白名单；用户配置及底层原始对象不进入复制通道。
  return redact({ apiVersion: 1, timestamp: new Date().toISOString(), app: { version: status.appVersion, backend: status.backend, label: status.label }, runtime: status.runtime,
    host: status.host, bridges: status.bridges, capabilities: status.capabilities, errors: status.errors,
    world: world ? {source:world.source,state:world.state,reason:world.reason,observedAt:world.observedAt,
      presentation:world.presentation??'unavailable',publisher:world.publisher??null,history:world.history??[],
      session:world.session ? {hostId:world.session.hostId,sessionId:world.session.sessionId,projectGeneration:world.session.projectGeneration} : null,
      target:world.target,capabilities:world.capabilities} : null,
    configuration: { state: config ? 'valid' : 'invalid', schemaVersion: config?.schemaVersion ?? null, verificationPreferencesApplied: false, experimentalWritesEnabled: false } });
}
