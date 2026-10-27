$ErrorActionPreference='Stop'
$ruledTaskRoot='D:\UE\Project\HorrorGame\SourceArt\Clipboard\RuledPaper'
$ruledTaskScript=Join-Path $ruledTaskRoot 'update_ue.py'
if (-not (Test-Path -LiteralPath $ruledTaskScript -PathType Leaf)) {throw ('Missing script: '+$ruledTaskScript)}
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
 throw 'Preserve the running UE editor. Save and close it before this exclusive texture update.'
}
$ruledTaskLog=Join-Path $ruledTaskRoot 'ue_update.log'
$ruledTaskReportPath=Join-Path $ruledTaskRoot 'ue_update_report.json'
$ruledTaskCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
$ruledTaskPrivateDDC='D:/UE/Project/HorrorGame/Saved/CodexDDC/EnvelopeReplacement'
try {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$ruledTaskPrivateDDC,'Process')
 $ruledTaskStartedUtc=(Get-Date).ToUniversalTime()
 $ruledTaskProcess=Start-Process -FilePath 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe' -WindowStyle Hidden -ArgumentList @(
  '"D:\UE\Project\HorrorGame\HorrorGame.uproject"','/Engine/Maps/Entry',
  ('"-ExecutePythonScript='+$ruledTaskScript.Replace('\','/')+'"'),
  '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-RenderOffscreen',
  '-nosplash','-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding',
  '-DDC=InstalledNoZenLocalFallback',
  ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path='+$ruledTaskPrivateDDC+',EnvPathOverride=UE-LocalDataCachePath)'),
  ('"-abslog='+$ruledTaskLog+'"')
 ) -PassThru -Wait
 $ruledTaskExit=$ruledTaskProcess.ExitCode
 [ordered]@{
  script='update_ue.py';pid=$ruledTaskProcess.Id;started_utc=$ruledTaskStartedUtc.ToString('o');
  completed_utc=(Get-Date).ToUniversalTime().ToString('o');exit_code=$ruledTaskExit;
  normal_zero_exit=($ruledTaskExit -eq 0);report=$ruledTaskReportPath;
  temporary_engine_world='/Engine/Maps/Entry';private_ddc=$ruledTaskPrivateDDC;
  allowed_target='/Game/Yastars/Mesh/Clipboard/Textures/T_ClipboardPaper_BaseColor'
 } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $ruledTaskRoot 'ue_update_completion.json') -Encoding utf8
 if ($ruledTaskExit -ne 0) {throw ('UE texture update helper exit '+$ruledTaskExit)}
 $ruledTaskReportFile=Get-Item -LiteralPath $ruledTaskReportPath
 if ($ruledTaskReportFile.LastWriteTimeUtc -lt $ruledTaskStartedUtc) {throw 'No fresh texture update report; Python may not have executed.'}
 $ruledTaskReport=Get-Content -LiteralPath $ruledTaskReportPath -Raw | ConvertFrom-Json
 if (-not $ruledTaskReport.success) {throw ('Clipboard texture update failed: '+$ruledTaskReport.error)}
 if (-not $ruledTaskReport.other_17_package_hashes_unchanged -or -not $ruledTaskReport.target_package_changed) {
  throw 'Texture update package hash audit did not pass.'
 }
 Write-Output 'CLIPBOARD_RULED_PAPER_UPDATE_COMPLETED_NORMAL_ZERO'
} finally {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$ruledTaskCache,'Process')
}
