$ErrorActionPreference = 'Stop'
$cabinetUE = $PSScriptRoot
$cabinetProject = (Resolve-Path (Join-Path $cabinetUE '..\..\..')).Path
$cabinetEditor = 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
$cabinetScript = (Join-Path $cabinetUE 'import_ue.py').Replace('\','/')
$cabinetLog = Join-Path $cabinetUE 'ue_import.log'
$cabinetReport = Join-Path $cabinetUE 'ue_import_report.json'
$cabinetPython = Join-Path $cabinetProject 'Tools\CLI-Anything\venv\Scripts\python.exe'
$cabinetDDC = (Join-Path $cabinetProject 'Saved\CodexDDC\EnvelopeReplacement').Replace('\','/')
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
    throw 'The user editor is running. Use run_live.py from its Output Log.'
}
$cabinetArgs = @(('"' + (Join-Path $cabinetProject 'HorrorGame.uproject') + '"'), '/Engine/Maps/Entry',
    ('"-ExecutePythonScript=' + $cabinetScript + '"'),
    '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-RenderOffscreen','-nosound','-nosplash',
    '-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding','-NoZenAutoLaunch','-DDC=InstalledNoZenLocalFallback',
    ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=' + $cabinetDDC + ',EnvPathOverride=UE-LocalDataCachePath)'),
    ('"-abslog=' + $cabinetLog + '"'))
$cabinetStart = (Get-Date).ToUniversalTime()
$cabinetPreviousDDC = [Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
try {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$cabinetDDC,'Process')
    $cabinetProcess = Start-Process -FilePath $cabinetEditor -WindowStyle Hidden -ArgumentList $cabinetArgs -PassThru -Wait
} finally {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$cabinetPreviousDDC,'Process')
}
if ($cabinetProcess.ExitCode -ne 0) { throw ('UE exit code: ' + $cabinetProcess.ExitCode) }
if ((Get-Item -LiteralPath $cabinetReport).LastWriteTimeUtc -lt $cabinetStart) { throw 'No fresh UE import report' }
$cabinetResult = Get-Content -LiteralPath $cabinetReport -Raw | ConvertFrom-Json
if (-not $cabinetResult.success) { throw $cabinetResult.error }
& $cabinetPython (Join-Path $cabinetUE 'verify_final.py')
if ($LASTEXITCODE -ne 0) { throw 'Saved cabinet verification failed' }
