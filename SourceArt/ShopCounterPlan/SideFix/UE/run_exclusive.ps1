$ErrorActionPreference='Stop'
$sideTaskDir=$PSScriptRoot
$sideProject='D:\UE\Project\HorrorGame'
$sideEditor='D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
$sideDDC=($sideProject+'\Saved\CodexDDC\EnvelopeReplacement').Replace('\','/')
$sidePreviousDDC=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
function Invoke-SidePhase([string]$entry,[string]$receipt) {
    if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {throw 'An editor is open; do not run concurrently'}
    $sideScript=(Join-Path $sideTaskDir $entry).Replace('\','/')
    $sideLog=Join-Path $sideTaskDir ($entry+'.log')
    $sideArguments=@(('"'+$sideProject+'\HorrorGame.uproject"'),'/Engine/Maps/Entry',('"-ExecutePythonScript='+$sideScript+'"'),
        '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-RenderOffscreen','-nosound','-nosplash',
        '-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding','-NoZenAutoLaunch','-DDC=InstalledNoZenLocalFallback',
        ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path='+$sideDDC+',EnvPathOverride=UE-LocalDataCachePath)'),
        ('"-abslog='+$sideLog+'"'))
    $sideStarted=(Get-Date).ToUniversalTime()
    try {
        [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$sideDDC,'Process')
        $sideProc=Start-Process -FilePath $sideEditor -WindowStyle Hidden -ArgumentList $sideArguments -PassThru -Wait
    } finally {[Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$sidePreviousDDC,'Process')}
    if ($sideProc.ExitCode -ne 0) {throw ('UE phase exit '+$sideProc.ExitCode)}
    $sideReceiptPath=Join-Path $sideTaskDir $receipt
    if ((Get-Item -LiteralPath $sideReceiptPath).LastWriteTimeUtc -lt $sideStarted) {throw 'No fresh repair receipt'}
    $sideResult=Get-Content -LiteralPath $sideReceiptPath -Raw | ConvertFrom-Json
    if (-not $sideResult.success) {throw $sideResult.error}
}
Invoke-SidePhase 'update_live.py' 'side_live_report.json'
Invoke-SidePhase 'verify_fresh.py' 'side_fresh_report.json'
Write-Output 'SIDE_FIX_IMPORTED_AND_RELOADED'
