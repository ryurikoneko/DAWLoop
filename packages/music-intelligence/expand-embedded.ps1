param([string]$Archive,[string]$Target)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# 显式使用系统 .NET，避免继承开发终端的 PSModulePath 后混用模块版本。
$stream = [System.IO.File]::OpenRead($Archive)
try { $digest = [System.Security.Cryptography.SHA256]::Create().ComputeHash($stream) } finally { $stream.Dispose() }
$hex = ([System.BitConverter]::ToString($digest)).Replace('-', '').ToLowerInvariant()
if ($hex -ne '009d6bf7e3b2ddca3d784fa09f90fe54336d5b60f0e0f305c37f400bf83cfd3b') { throw 'MI_MODEL_HASH_REJECTED' }
if ([System.IO.Directory]::Exists($Target) -or [System.IO.File]::Exists($Target)) { throw 'MI_ENVIRONMENT_EXISTS' }
$framework = [System.Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory()
[void][System.Reflection.Assembly]::LoadFrom([System.IO.Path]::Combine($framework, 'System.IO.Compression.FileSystem.dll'))
$zip = [System.IO.Compression.ZipFile]::OpenRead($Archive)
try {
    $root = [System.IO.Path]::GetFullPath($Target) + [System.IO.Path]::DirectorySeparatorChar
    foreach ($entry in $zip.Entries) {
        $resolved = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($Target, $entry.FullName))
        if (-not $resolved.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'MI_ARCHIVE_PATH_REJECTED' }
    }
} finally { $zip.Dispose() }
[System.IO.Compression.ZipFile]::ExtractToDirectory($Archive, $Target)
