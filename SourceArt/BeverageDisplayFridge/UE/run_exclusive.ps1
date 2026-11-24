$ErrorActionPreference = 'Stop'
$cabinetUE = $PSScriptRoot
$cabinetProject = (Resolve-Path (Join-Path $cabinetUE '..\..\..')).Path
$cabinetEditor = 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
$cabinetScript = (Join-Path $cabinetUE 'fridge_import.py').Replace('\','/')
$cabinetLog = Join-Path $cabinetUE 'ue_import.log'
$cabinetReport = Join-Path $cabinetUE 'ue_import_report.json'
$cabinetPython = Join-Path $cabinetProject 'Tools\CLI-Anything\venv\Scripts\python.exe'
$cabinetDDC = (Join-Path $cabinetProject 'Saved\CodexDDC\BeverageDisplayFridge').Replace('\','/')
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
    throw 'The user editor is running. Use run_live.py from its Output Log.'
}
& $cabinetPython -c "import sys;sys.path.insert(0,r'$cabinetUE');import fridge_manifest as c;m,r,e,s=c.read_export();print('FRIDGE_PREFLIGHT',len(r),sum(v['triangles'] for v in r.values()),len(e))"
if ($LASTEXITCODE -ne 0) { throw 'Fridge export preflight failed' }
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
$cabinetFreshScript = (Join-Path $cabinetUE 'verify_fresh_editor.py').Replace('\','/')
$cabinetFreshLog = Join-Path $cabinetUE 'ue_verify_fresh.log'
$cabinetFreshReport = Join-Path $cabinetUE 'fresh_editor_verification.json'
$cabinetFreshArgs = @($cabinetArgs | ForEach-Object {
    if ($_ -like '*-ExecutePythonScript=*') { '"-ExecutePythonScript=' + $cabinetFreshScript + '"' }
    elseif ($_ -like '*-abslog=*') { '"-abslog=' + $cabinetFreshLog + '"' }
    else { $_ }
})
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
    throw 'An editor opened after import. Fresh reload remains pending.'
}
$cabinetFreshStart = (Get-Date).ToUniversalTime()
try {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$cabinetDDC,'Process')
    $cabinetFreshProcess = Start-Process -FilePath $cabinetEditor -WindowStyle Hidden -ArgumentList $cabinetFreshArgs -PassThru -Wait
} finally {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$cabinetPreviousDDC,'Process')
}
if ($cabinetFreshProcess.ExitCode -ne 0) { throw ('Fresh UE exit code: ' + $cabinetFreshProcess.ExitCode) }
if ((Get-Item -LiteralPath $cabinetFreshReport).LastWriteTimeUtc -lt $cabinetFreshStart) { throw 'No fresh reload report' }
$cabinetFreshResult = Get-Content -LiteralPath $cabinetFreshReport -Raw | ConvertFrom-Json
if (-not $cabinetFreshResult.success) { throw $cabinetFreshResult.error }
& $cabinetPython (Join-Path $cabinetUE 'verify_final.py') --require-fresh
if ($LASTEXITCODE -ne 0) { throw 'Fresh cabinet verification failed' }

