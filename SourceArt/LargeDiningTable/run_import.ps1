$ErrorActionPreference='Stop'
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {throw 'Preserve the running editor; do not launch a second writer.'}
$diningSource='D:\UE\Project\HorrorGame\SourceArt\LargeDiningTable'
$diningCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
try {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath','D:\UE\Project\HorrorGame\Saved\CodexDDC','Process')
 $diningStarted=(Get-Date).ToUniversalTime().ToString('o')
 $diningProcess=Start-Process -FilePath 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe' -WindowStyle Hidden -ArgumentList @(
  '"D:\UE\Project\HorrorGame\HorrorGame.uproject"','/Engine/Maps/Entry',
  '"-ExecutePythonScript=D:/UE/Project/HorrorGame/SourceArt/LargeDiningTable/import_ue.py"',
  '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-RenderOffscreen',
  '-nosplash','-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding',
  '"-ExecCmds=Interchange.FeatureFlags.Import.FBX 0"',
  '-DDC=InstalledNoZenLocalFallback',
  '-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=D:/UE/Project/HorrorGame/Saved/CodexDDC,EnvPathOverride=UE-LocalDataCachePath)',
  '"-abslog=D:\UE\Project\HorrorGame\SourceArt\LargeDiningTable\ue_auto_import.log"'
 ) -PassThru -Wait
 $diningExit=$diningProcess.ExitCode
 [ordered]@{pid=$diningProcess.Id;started_utc=$diningStarted;completed_utc=(Get-Date).ToUniversalTime().ToString('o');exit_code=$diningExit;normal_zero_exit=($diningExit -eq 0)} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $diningSource 'ue_import_completion.json') -Encoding utf8
 if ($diningExit -ne 0) {throw ('UE helper exit '+$diningExit)}
 $diningReport=Get-Content -LiteralPath (Join-Path $diningSource 'ue_import_report.json') -Raw | ConvertFrom-Json
 if (-not $diningReport.success) {throw $diningReport.error}
 Write-Output 'DINING_IMPORT_COMPLETED_NORMAL_ZERO'
} finally {[Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$diningCache,'Process')}
