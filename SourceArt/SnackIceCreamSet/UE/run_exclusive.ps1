param([switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
$goodsUE = $PSScriptRoot
$goodsProject = (Resolve-Path (Join-Path $goodsUE '..\..\..')).Path
$goodsEditor = 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
$goodsPython = Join-Path $goodsProject 'Tools\CLI-Anything\venv\Scripts\python.exe'
# Reuse the populated cache from the prior cardboard import. Never create a cold cache.
$goodsDDC = (Join-Path $goodsProject 'Saved\CodexDDC\CardboardBoxSet').Replace('\','/')
function Assert-GoodsEditorClosed {
    if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
        throw 'An Unreal editor is running. Close it before starting the exclusive goods helper.'
    }
}
function Invoke-GoodsEditorCheck([string]$ScriptName, [string]$ReportName, [string]$LogName) {
    Assert-GoodsEditorClosed
    $goodsScript = (Join-Path $goodsUE $ScriptName).Replace('\','/')
    $goodsReport = Join-Path $goodsUE $ReportName
    $goodsLog = Join-Path $goodsUE $LogName
    $goodsArgs = @(
        ('"' + (Join-Path $goodsProject 'HorrorGame.uproject') + '"'), '/Engine/Maps/Entry',
        ('"-ExecutePythonScript=' + $goodsScript + '"'),
        '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities', '-unattended', '-RenderOffscreen',
        '-nosound', '-nosplash', '-nop4', '-NOINI', '-NoAutoSave', '-nocef', '-NoLiveCoding',
        '-NoZenAutoLaunch', '-DDC=InstalledNoZenLocalFallback',
        ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=' + $goodsDDC + ',EnvPathOverride=UE-LocalDataCachePath)'),
        ('"-abslog=' + $goodsLog + '"')
    )
    $goodsStart = (Get-Date).ToUniversalTime()
    $goodsPreviousDDC = [Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
    try {
        [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$goodsDDC,'Process')
        Assert-GoodsEditorClosed
        $goodsProcess = Start-Process -FilePath $goodsEditor -WindowStyle Hidden -ArgumentList $goodsArgs -PassThru -Wait
    } finally {
        [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$goodsPreviousDDC,'Process')
    }
    if ($goodsProcess.ExitCode -ne 0) { throw ('UE exit code: ' + $goodsProcess.ExitCode) }
    if (-not (Test-Path -LiteralPath $goodsReport)) { throw 'No goods result report' }
    if ((Get-Item -LiteralPath $goodsReport).LastWriteTimeUtc -lt $goodsStart) { throw 'No fresh goods report' }
    $goodsResult = Get-Content -LiteralPath $goodsReport -Raw | ConvertFrom-Json
    if (-not $goodsResult.success) { throw $goodsResult.error }
}
Assert-GoodsEditorClosed
if (-not (Test-Path -LiteralPath $goodsEditor -PathType Leaf)) { throw 'Unreal editor executable missing' }
if (-not (Test-Path -LiteralPath $goodsDDC -PathType Container)) { throw 'Existing warm cardboard cache missing' }
if (-not @(Get-ChildItem -LiteralPath $goodsDDC -Force | Select-Object -First 1).Count) { throw 'Existing cardboard cache is empty' }
if (Test-Path -LiteralPath (Join-Path $goodsUE 'source_update.lock')) { throw 'Source is still being authored' }
$goodsPreflight = @((Join-Path $goodsUE 'goods_manifest.py'))
if (-not $VerifyOnly) { $goodsPreflight += '--snapshot' }
& $goodsPython @goodsPreflight
if ($LASTEXITCODE -ne 0) { throw 'Goods export preflight failed' }
if (-not $VerifyOnly) {
    Invoke-GoodsEditorCheck 'goods_import.py' 'ue_import_report.json' 'ue_import.log'
    & $goodsPython (Join-Path $goodsUE 'verify_final.py')
    if ($LASTEXITCODE -ne 0) { throw 'Saved goods package verification failed' }
}
Invoke-GoodsEditorCheck 'verify_fresh_editor.py' 'fresh_editor_verification.json' 'ue_verify_fresh.log'
& $goodsPython (Join-Path $goodsUE 'verify_final.py') --require-fresh
if ($LASTEXITCODE -ne 0) { throw 'Fresh goods verification failed' }
