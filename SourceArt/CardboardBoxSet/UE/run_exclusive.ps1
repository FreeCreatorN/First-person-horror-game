param([switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
$cartonUE = $PSScriptRoot
$cartonProject = (Resolve-Path (Join-Path $cartonUE '..\..\..')).Path
$cartonEditor = 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
$cartonPython = Join-Path $cartonProject 'Tools\CLI-Anything\venv\Scripts\python.exe'
$cartonDDC = (Join-Path $cartonProject 'Saved\CodexDDC\CardboardBoxSet').Replace('\','/')
function Assert-CartonEditorClosed {
    if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
        throw 'An Unreal editor is running. Close it before starting the exclusive cardboard helper.'
    }
}
function Invoke-CartonEditorCheck([string]$ScriptName, [string]$ReportName, [string]$LogName) {
    Assert-CartonEditorClosed
    $cartonScript = (Join-Path $cartonUE $ScriptName).Replace('\','/')
    $cartonReport = Join-Path $cartonUE $ReportName
    $cartonLog = Join-Path $cartonUE $LogName
    $cartonArgs = @(
        ('"' + (Join-Path $cartonProject 'HorrorGame.uproject') + '"'), '/Engine/Maps/Entry',
        ('"-ExecutePythonScript=' + $cartonScript + '"'),
        '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities', '-unattended', '-RenderOffscreen',
        '-nosound', '-nosplash', '-nop4', '-NOINI', '-NoAutoSave', '-nocef', '-NoLiveCoding',
        '-NoZenAutoLaunch', '-DDC=InstalledNoZenLocalFallback',
        ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=' + $cartonDDC + ',EnvPathOverride=UE-LocalDataCachePath)'),
        ('"-abslog=' + $cartonLog + '"')
    )
    $cartonStart = (Get-Date).ToUniversalTime()
    $cartonPreviousDDC = [Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
    try {
        [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$cartonDDC,'Process')
        # Recheck immediately before launching, and keep the helper window hidden.
        Assert-CartonEditorClosed
        $cartonProcess = Start-Process -FilePath $cartonEditor -WindowStyle Hidden -ArgumentList $cartonArgs -PassThru -Wait
    } finally {
        [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$cartonPreviousDDC,'Process')
    }
    if ($cartonProcess.ExitCode -ne 0) { throw ('UE exit code: ' + $cartonProcess.ExitCode) }
    if ((Get-Item -LiteralPath $cartonReport).LastWriteTimeUtc -lt $cartonStart) { throw 'No fresh cardboard report' }
    $cartonResult = Get-Content -LiteralPath $cartonReport -Raw | ConvertFrom-Json
    if (-not $cartonResult.success) { throw $cartonResult.error }
}
Assert-CartonEditorClosed
& $cartonPython -c "import sys;sys.path.insert(0,r'$cartonUE');import carton_manifest as c;m,r,e,s=c.read_export();print('CARTON_PREFLIGHT',len(r),sum(v['triangles'] for v in r.values()),len(e))"
if ($LASTEXITCODE -ne 0) { throw 'Cardboard export preflight failed' }
if (-not $VerifyOnly) {
    Invoke-CartonEditorCheck 'carton_import.py' 'ue_import_report.json' 'ue_import.log'
    & $cartonPython (Join-Path $cartonUE 'verify_final.py')
    if ($LASTEXITCODE -ne 0) { throw 'Saved cardboard package verification failed' }
}
Invoke-CartonEditorCheck 'verify_fresh_editor.py' 'fresh_editor_verification.json' 'ue_verify_fresh.log'
& $cartonPython (Join-Path $cartonUE 'verify_final.py') --require-fresh
if ($LASTEXITCODE -ne 0) { throw 'Fresh cardboard verification failed' }
