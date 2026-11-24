param([switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
$sofaUE = $PSScriptRoot
$sofaProject = (Resolve-Path (Join-Path $sofaUE '..\..\..')).Path
$sofaEditor = 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
$sofaPython = Join-Path $sofaProject 'Tools\CLI-Anything\venv\Scripts\python.exe'
# Reuse the populated cache from the prior cardboard import. Never create a cold cache.
$sofaDDC = (Join-Path $sofaProject 'Saved\CodexDDC\CardboardBoxSet').Replace('\','/')
function Assert-SofaEditorClosed {
    if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
        throw 'An Unreal editor is running. Close it before starting the exclusive sofa helper.'
    }
}
function Invoke-SofaEditorCheck([string]$ScriptName, [string]$ReportName, [string]$LogName) {
    Assert-SofaEditorClosed
    $sofaScript = (Join-Path $sofaUE $ScriptName).Replace('\','/')
    $sofaReport = Join-Path $sofaUE $ReportName
    $sofaLog = Join-Path $sofaUE $LogName
    $sofaArgs = @(
        ('"' + (Join-Path $sofaProject 'HorrorGame.uproject') + '"'), '/Engine/Maps/Entry',
        ('"-ExecutePythonScript=' + $sofaScript + '"'),
        '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities', '-unattended', '-RenderOffscreen',
        '-nosound', '-nosplash', '-nop4', '-NOINI', '-NoAutoSave', '-nocef', '-NoLiveCoding',
        '-NoZenAutoLaunch', '-DDC=InstalledNoZenLocalFallback',
        ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=' + $sofaDDC + ',EnvPathOverride=UE-LocalDataCachePath)'),
        ('"-abslog=' + $sofaLog + '"')
    )
    $sofaStart = (Get-Date).ToUniversalTime()
    $sofaPreviousDDC = [Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
    try {
        [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$sofaDDC,'Process')
        Assert-SofaEditorClosed
        $sofaProcess = Start-Process -FilePath $sofaEditor -WindowStyle Hidden -ArgumentList $sofaArgs -PassThru -Wait
    } finally {
        [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$sofaPreviousDDC,'Process')
    }
    if ($sofaProcess.ExitCode -ne 0) { throw ('UE exit code: ' + $sofaProcess.ExitCode) }
    if (-not (Test-Path -LiteralPath $sofaReport)) { throw 'No sofa result report' }
    if ((Get-Item -LiteralPath $sofaReport).LastWriteTimeUtc -lt $sofaStart) { throw 'No fresh sofa report' }
    $sofaResult = Get-Content -LiteralPath $sofaReport -Raw | ConvertFrom-Json
    if (-not $sofaResult.success) { throw $sofaResult.error }
}
Assert-SofaEditorClosed
if (-not (Test-Path -LiteralPath $sofaEditor -PathType Leaf)) { throw 'Unreal editor executable missing' }
if (-not (Test-Path -LiteralPath $sofaDDC -PathType Container)) { throw 'Existing warm cardboard cache missing' }
if (-not @(Get-ChildItem -LiteralPath $sofaDDC -Force | Select-Object -First 1).Count) { throw 'Existing cardboard cache is empty' }
if (Test-Path -LiteralPath (Join-Path $sofaUE 'source_update.lock')) { throw 'Source is still being authored' }
$sofaPreflight = @((Join-Path $sofaUE 'sofa_manifest.py'))
if (-not $VerifyOnly) { $sofaPreflight += '--snapshot' }
& $sofaPython @sofaPreflight
if ($LASTEXITCODE -ne 0) { throw 'Sofa export preflight failed' }
if (-not $VerifyOnly) {
    Invoke-SofaEditorCheck 'sofa_import.py' 'ue_import_report.json' 'ue_import.log'
    & $sofaPython (Join-Path $sofaUE 'verify_final.py')
    if ($LASTEXITCODE -ne 0) { throw 'Saved sofa package verification failed' }
}
Invoke-SofaEditorCheck 'verify_fresh_editor.py' 'fresh_editor_verification.json' 'ue_verify_fresh.log'
& $sofaPython (Join-Path $sofaUE 'verify_final.py') --require-fresh
if ($LASTEXITCODE -ne 0) { throw 'Fresh sofa verification failed' }
