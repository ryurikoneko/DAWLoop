import type { DesktopBridge } from '../../../packages/shared-types/contracts';

// 编译器必须拒绝越界方法、错误参数与伪造结果类型；函数不在运行时调用。
export async function checkDesktopContract(bridge: DesktopBridge) {
  const status = await bridge.call('getAppStatus');
  if (status.ok) {
    const backend: 'real' | 'mock' = status.data.backend;
    void backend;
    // @ts-expect-error 状态结果不能冒充配置。
    const config: { schemaVersion: 1 } = status.data;
    void config;
  }
  await bridge.call('updateConfig', { ui: { language: 'zh-CN' } });
  // @ts-expect-error 新 Core 方法不能自动成为 Renderer 方法。
  await bridge.call('plugin.parameter.write', { value: 1 });
  // @ts-expect-error 方法名必须受合同限制。
  await bridge.call('asdfghjkl');
  // @ts-expect-error 修改方法不能缺少参数。
  await bridge.call('updateConfig');
  // @ts-expect-error 语言字段只能使用支持的语言。
  await bridge.call('updateConfig', { ui: { language: 'other' } });
  // @ts-expect-error 无参数方法不能传入任意对象。
  await bridge.call('getConfig', {});
}
