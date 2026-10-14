export async function exportDiagnosticReport({ reportText, chooseFile, writeFile }) {
  const failure = code => ({ apiVersion:1, ok:false, error:{ code, category:'desktop', message:code, recoverable:true } });
  if (typeof reportText !== 'string' || Buffer.byteLength(reportText, 'utf8') > 1024 * 1024) return failure('DIAGNOSTIC_REPORT_REQUIRED');
  try {
    const selected = await chooseFile();
    if (selected.canceled) return { apiVersion:1, ok:true, data:{ saved:false } };
    if (!selected.filePath) return failure('DIAGNOSTIC_EXPORT_FAILED');
    // 内容由主进程缓存，路径由原生对话框决定；Renderer 不提供任何文件写入参数。
    await writeFile(selected.filePath, reportText, 'utf8');
    return { apiVersion:1, ok:true, data:{ saved:true } };
  } catch { return failure('DIAGNOSTIC_EXPORT_FAILED'); }
}
