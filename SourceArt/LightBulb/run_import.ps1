$ErrorActionPreference='Stop'
$lightbulbTaskRoot='D:\UE\Project\HorrorGame\SourceArt\LightBulb'
$lightbulbTaskScript=Join-Path $lightbulbTaskRoot 'import_ue.py'
if (-not (Test-Path -LiteralPath $lightbulbTaskScript -PathType Leaf)) {throw ('Missing script: '+$lightbulbTaskScript)}
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
 throw 'Preserve the running UE editor. Save and close it before launching this exclusive import.'
}
$lightbulbTaskLog=Join-Path $lightbulbTaskRoot 'ue_import.log'
$lightbulbTaskReportPath=Join-Path $lightbulbTaskRoot 'ue_import_report.json'
$lightbulbTaskCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
$lightbulbTaskPrivateDDC='D:/UE/Project/HorrorGame/Saved/CodexDDC/EnvelopeReplacement'
try {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$lightbulbTaskPrivateDDC,'Process')
 $lightbulbTaskStartedUtc=(Get-Date).ToUniversalTime()
 $lightbulbTaskProcess=Start-Process -FilePath 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe' -WindowStyle Hidden -ArgumentList @(
  '"D:\UE\Project\HorrorGame\HorrorGame.uproject"','/Engine/Maps/Entry',
  ('"-ExecutePythonScript='+$lightbulbTaskScript.Replace('\','/')+'"'),
  '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-RenderOffscreen',
  '-nosplash','-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding',
  '"-ExecCmds=Interchange.FeatureFlags.Import.FBX 0"',
  '-DDC=InstalledNoZenLocalFallback',
  ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path='+$lightbulbTaskPrivateDDC+',EnvPathOverride=UE-LocalDataCachePath)'),
  ('"-abslog='+$lightbulbTaskLog+'"')
 ) -PassThru -Wait
 $lightbulbTaskExit=$lightbulbTaskProcess.ExitCode
 [ordered]@{
  script='import_ue.py';pid=$lightbulbTaskProcess.Id;started_utc=$lightbulbTaskStartedUtc.ToString('o');
  completed_utc=(Get-Date).ToUniversalTime().ToString('o');exit_code=$lightbulbTaskExit;
  normal_zero_exit=($lightbulbTaskExit -eq 0);report=$lightbulbTaskReportPath;
  temporary_engine_world='/Engine/Maps/Entry';private_ddc=$lightbulbTaskPrivateDDC;
  target_root='/Game/Yastars/Mesh/LightBulb'
 } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $lightbulbTaskRoot 'ue_import_completion.json') -Encoding utf8
 if ($lightbulbTaskExit -ne 0) {throw ('UE import helper exit '+$lightbulbTaskExit)}
 $lightbulbTaskReportFile=Get-Item -LiteralPath $lightbulbTaskReportPath
 if ($lightbulbTaskReportFile.LastWriteTimeUtc -lt $lightbulbTaskStartedUtc) {
  throw 'No fresh import report; Python may not have executed.'
 }
 $lightbulbTaskReport=Get-Content -LiteralPath $lightbulbTaskReportPath -Raw | ConvertFrom-Json
 if (-not $lightbulbTaskReport.success) {throw ('LightBulb import failed: '+$lightbulbTaskReport.error)}
 if ($lightbulbTaskReport.new_package_count -ne 8) {throw 'LightBulb import package count did not match 8.'}
 Write-Output 'LIGHTBULB_IMPORT_COMPLETED_NORMAL_ZERO'
} finally {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$lightbulbTaskCache,'Process')
}
