// Renderer 权限独立维护，Core 新方法不能自动获得桌面调用权限。
const allowed = new Set(['getWorldSnapshot','getDesktopEnvironment','getAppStatus','getRuntimeStatus','getHostStatus','getBridgeStatus','getCapabilities','startRuntime','stopRuntime','getConfig','updateConfig','getProfiles','createProfile','updateProfile','getActiveProfile','setActiveProfile','getDiagnostics','getRecentLogs','testHostPath','detectHostPath']);
const developmentOnly = new Set(['setBackend','setMockScenario']);
export function desktopDevelopment(isPackaged, args) {
  return !isPackaged && (args.includes('--dev') || args.includes('--mock'));
}
export function rendererMethodAllowed(method, development = false) {
  return typeof method === 'string' && (allowed.has(method) || (development && developmentOnly.has(method)));
}
