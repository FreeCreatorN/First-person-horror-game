$ErrorActionPreference='Stop'
$candleTaskRoot='D:\UE\Project\HorrorGame\SourceArt\Candle'
$candleTaskScript=Join-Path $candleTaskRoot 'import_ue.py'
if (-not (Test-Path -LiteralPath $candleTaskScript -PathType Leaf)) {throw ('Missing script: '+$candleTaskScript)}
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
 throw 'Preserve the running UE editor. Save and close it before launching this exclusive import.'
}
$candleTaskLog=Join-Path $candleTaskRoot 'ue_import.log'
$candleTaskReportPath=Join-Path $candleTaskRoot 'ue_import_report.json'
$candleTaskCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
$candleTaskPrivateDDC='D:/UE/Project/HorrorGame/Saved/CodexDDC/EnvelopeReplacement'
try {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$candleTaskPrivateDDC,'Process')
 $candleTaskStartedUtc=(Get-Date).ToUniversalTime()
 $candleTaskProcess=Start-Process -FilePath 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe' -WindowStyle Hidden -ArgumentList @(
  '"D:\UE\Project\HorrorGame\HorrorGame.uproject"','/Engine/Maps/Entry',
  ('"-ExecutePythonScript='+$candleTaskScript.Replace('\','/')+'"'),
  '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-RenderOffscreen',
  '-nosplash','-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding',
  '"-ExecCmds=Interchange.FeatureFlags.Import.FBX 0"',
  '-DDC=InstalledNoZenLocalFallback',
  ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path='+$candleTaskPrivateDDC+',EnvPathOverride=UE-LocalDataCachePath)'),
  ('"-abslog='+$candleTaskLog+'"')
 ) -PassThru -Wait
 $candleTaskExit=$candleTaskProcess.ExitCode
 [ordered]@{
  script='import_ue.py';pid=$candleTaskProcess.Id;started_utc=$candleTaskStartedUtc.ToString('o');
  completed_utc=(Get-Date).ToUniversalTime().ToString('o');exit_code=$candleTaskExit;
  normal_zero_exit=($candleTaskExit -eq 0);report=$candleTaskReportPath;
  temporary_engine_world='/Engine/Maps/Entry';private_ddc=$candleTaskPrivateDDC;
  target_root='/Game/Yastars/Mesh/Candle'
 } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $candleTaskRoot 'ue_import_completion.json') -Encoding utf8
 if ($candleTaskExit -ne 0) {throw ('UE import helper exit '+$candleTaskExit)}
 $candleTaskReportFile=Get-Item -LiteralPath $candleTaskReportPath
 if ($candleTaskReportFile.LastWriteTimeUtc -lt $candleTaskStartedUtc) {
  throw 'No fresh import report; Python may not have executed.'
 }
 $candleTaskReport=Get-Content -LiteralPath $candleTaskReportPath -Raw | ConvertFrom-Json
 if (-not $candleTaskReport.success) {throw ('Candle import failed: '+$candleTaskReport.error)}
 if ($candleTaskReport.new_package_count -ne 6) {throw 'Candle import package count did not match 6.'}
 Write-Output 'CANDLE_IMPORT_COMPLETED_NORMAL_ZERO'
} finally {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$candleTaskCache,'Process')
}
