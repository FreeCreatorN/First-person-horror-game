$ErrorActionPreference='Stop'
$clipboardTaskRoot='D:\UE\Project\HorrorGame\SourceArt\Clipboard'
$clipboardTaskScript=Join-Path $clipboardTaskRoot 'import_ue.py'
if (-not (Test-Path -LiteralPath $clipboardTaskScript -PathType Leaf)) {throw ('Missing script: '+$clipboardTaskScript)}
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
 throw 'Preserve the running UE editor. Save and close it before launching this exclusive import.'
}
$clipboardTaskLog=Join-Path $clipboardTaskRoot 'ue_import.log'
$clipboardTaskReportPath=Join-Path $clipboardTaskRoot 'ue_import_report.json'
$clipboardTaskCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
$clipboardTaskPrivateDDC='D:/UE/Project/HorrorGame/Saved/CodexDDC/EnvelopeReplacement'
try {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$clipboardTaskPrivateDDC,'Process')
 $clipboardTaskStartedUtc=(Get-Date).ToUniversalTime()
 $clipboardTaskProcess=Start-Process -FilePath 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe' -WindowStyle Hidden -ArgumentList @(
  '"D:\UE\Project\HorrorGame\HorrorGame.uproject"','/Engine/Maps/Entry',
  ('"-ExecutePythonScript='+$clipboardTaskScript.Replace('\','/')+'"'),
  '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-RenderOffscreen',
  '-nosplash','-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding',
  '"-ExecCmds=Interchange.FeatureFlags.Import.FBX 0"',
  '-DDC=InstalledNoZenLocalFallback',
  ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path='+$clipboardTaskPrivateDDC+',EnvPathOverride=UE-LocalDataCachePath)'),
  ('"-abslog='+$clipboardTaskLog+'"')
 ) -PassThru -Wait
 $clipboardTaskExit=$clipboardTaskProcess.ExitCode
 [ordered]@{
  script='import_ue.py';pid=$clipboardTaskProcess.Id;started_utc=$clipboardTaskStartedUtc.ToString('o');
  completed_utc=(Get-Date).ToUniversalTime().ToString('o');exit_code=$clipboardTaskExit;
  normal_zero_exit=($clipboardTaskExit -eq 0);report=$clipboardTaskReportPath;
  temporary_engine_world='/Engine/Maps/Entry';private_ddc=$clipboardTaskPrivateDDC;
  target_root='/Game/Yastars/Mesh/Clipboard'
 } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $clipboardTaskRoot 'ue_import_completion.json') -Encoding utf8
 if ($clipboardTaskExit -ne 0) {throw ('UE import helper exit '+$clipboardTaskExit)}
 $clipboardTaskReportFile=Get-Item -LiteralPath $clipboardTaskReportPath
 if ($clipboardTaskReportFile.LastWriteTimeUtc -lt $clipboardTaskStartedUtc) {
  throw 'No fresh import report; Python may not have executed.'
 }
 $clipboardTaskReport=Get-Content -LiteralPath $clipboardTaskReportPath -Raw | ConvertFrom-Json
 if (-not $clipboardTaskReport.success) {throw ('Clipboard import failed: '+$clipboardTaskReport.error)}
 if ($clipboardTaskReport.new_package_count -ne 18) {throw 'Clipboard import package count did not match 18.'}
 Write-Output 'CLIPBOARD_IMPORT_COMPLETED_NORMAL_ZERO'
} finally {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$clipboardTaskCache,'Process')
}
