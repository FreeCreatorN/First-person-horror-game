$ErrorActionPreference = 'Stop'
$counterUE = $PSScriptRoot
$counterProject = (Resolve-Path (Join-Path $counterUE '..\..\..')).Path
$counterEditor = 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
$counterPython = Join-Path $counterProject 'Tools\CLI-Anything\venv\Scripts\python.exe'
$counterDDC = (Join-Path $counterProject 'Saved\CodexDDC\EnvelopeReplacement').Replace('\','/')
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
    throw 'An editor is already running; use the current editor rather than concurrent writes.'
}
& $counterPython -c "import sys;sys.path.insert(0,r'$counterUE');import empty_manifest as c;m,r,e,s=c.read_export();print('EMPTY_COUNTER_PREFLIGHT',len(r),sum(v['triangles'] for v in r.values()))"
if ($LASTEXITCODE -ne 0) { throw 'Export preflight failed before launching UE' }
$counterPreviousDDC = [Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
function Invoke-CounterUEPhase([string]$counterEntry,[string]$counterLogName,[string]$counterReportName) {
    if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
        throw 'An editor opened before this phase; no concurrent editor writes permitted.'
    }
    $counterScript = (Join-Path $counterUE $counterEntry).Replace('\','/')
    $counterLog = Join-Path $counterUE $counterLogName
    $counterReport = Join-Path $counterUE $counterReportName
    $counterArgs = @(('"' + (Join-Path $counterProject 'HorrorGame.uproject') + '"'), '/Engine/Maps/Entry',
        ('"-ExecutePythonScript=' + $counterScript + '"'),
        '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-RenderOffscreen','-nosound','-nosplash',
        '-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding','-NoZenAutoLaunch','-DDC=InstalledNoZenLocalFallback',
        ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=' + $counterDDC + ',EnvPathOverride=UE-LocalDataCachePath)'),
        ('"-abslog=' + $counterLog + '"'))
    $counterStart = (Get-Date).ToUniversalTime()
    try {
        [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$counterDDC,'Process')
        $counterProcess = Start-Process -FilePath $counterEditor -WindowStyle Hidden -ArgumentList $counterArgs -PassThru -Wait
    } finally {
        [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$counterPreviousDDC,'Process')
    }
    if ($counterProcess.ExitCode -ne 0) { throw ('UE exit code: '+$counterProcess.ExitCode) }
    if ((Get-Item -LiteralPath $counterReport).LastWriteTimeUtc -lt $counterStart) { throw 'No fresh UE phase report' }
    $counterResult = Get-Content -LiteralPath $counterReport -Raw | ConvertFrom-Json
    if (-not $counterResult.success) { throw $counterResult.error }
}
Invoke-CounterUEPhase 'replace_empty_ue.py' 'ue_empty_replacement.log' 'ue_empty_replacement_report.json'
& $counterPython (Join-Path $counterUE 'verify_empty_final.py')
if ($LASTEXITCODE -ne 0) { throw 'Replacement verification failed' }
Invoke-CounterUEPhase 'verify_empty_fresh.py' 'ue_empty_fresh.log' 'empty_fresh_verification.json'
& $counterPython (Join-Path $counterUE 'verify_empty_final.py') --require-fresh
if ($LASTEXITCODE -ne 0) { throw 'Fresh empty counter verification failed' }
