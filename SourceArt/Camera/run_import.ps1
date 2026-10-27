param(
 [switch]$FinalizeConsole,
 [int]$ExistingEditorPid,
 [string]$StartedUtc,
 [string]$ExpectedScriptSha256
)
$ErrorActionPreference='Stop'
$cameraTaskRoot='D:\UE\Project\HorrorGame\SourceArt\Camera'
$cameraTaskScript=Join-Path $cameraTaskRoot 'import_ue.py'
if (-not (Test-Path -LiteralPath $cameraTaskScript -PathType Leaf)) {throw ('Missing script: '+$cameraTaskScript)}
$cameraTaskReportPath=Join-Path $cameraTaskRoot 'ue_import_report.json'
if ($FinalizeConsole) {
 # This mode only verifies an already completed GUI console command. It never
 # starts, stops, remotely controls, saves, or sends commands to the editor.
 if (-not $ExistingEditorPid -or -not $StartedUtc -or -not $ExpectedScriptSha256) {
  throw 'Finalization needs ExistingEditorPid, StartedUtc captured before the GUI command, and ExpectedScriptSha256 captured before the GUI command.'
 }
 if ($ExpectedScriptSha256 -notmatch '^[a-fA-F0-9]{64}$') {throw 'ExpectedScriptSha256 must be a SHA256 digest.'}
 if ($StartedUtc -notmatch '(Z|[+-]\d\d:\d\d)$') {throw 'StartedUtc must include a UTC offset.'}
 $cameraTaskBegan=([DateTimeOffset]::Parse($StartedUtc)).UtcDateTime
 $cameraTaskNow=(Get-Date).ToUniversalTime()
 if ($cameraTaskBegan -gt $cameraTaskNow) {throw 'The GUI command start time is in the future.'}
 $cameraTaskEditor=Get-CimInstance Win32_Process -Filter ('ProcessId='+$ExistingEditorPid)
 if (-not $cameraTaskEditor -or $cameraTaskEditor.Name -ne 'UnrealEditor.exe') {throw 'The original UE editor process is not running.'}
 if ($cameraTaskEditor.ExecutablePath -ine 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe') {throw 'Unexpected UE editor executable.'}
 if ($cameraTaskEditor.CommandLine -notmatch 'D:[/\\]UE[/\\]Project[/\\]HorrorGame[/\\]HorrorGame\.uproject') {throw 'The existing editor is not the HorrorGame project.'}
 $cameraTaskCreatedUtc=$cameraTaskEditor.CreationDate.ToUniversalTime()
 if ($cameraTaskCreatedUtc -gt $cameraTaskBegan) {throw 'The editor process was created after the GUI command began.'}
 $cameraTaskScriptSha=(Get-FileHash -LiteralPath $cameraTaskScript -Algorithm SHA256).Hash.ToLowerInvariant()
 if ($cameraTaskScriptSha -ne $ExpectedScriptSha256.ToLowerInvariant()) {throw 'Import script changed after the GUI command was prepared.'}
 $cameraTaskReportFile=Get-Item -LiteralPath $cameraTaskReportPath
 $cameraTaskReport=Get-Content -LiteralPath $cameraTaskReportPath -Raw | ConvertFrom-Json
 if ($cameraTaskReportFile.LastWriteTimeUtc -lt $cameraTaskBegan) {throw 'No fresh console import report exists.'}
 $cameraTaskImportBegan=([DateTimeOffset]::Parse($cameraTaskReport.started_utc)).UtcDateTime
 $cameraTaskImportEnded=([DateTimeOffset]::Parse($cameraTaskReport.completed_utc)).UtcDateTime
 if ($cameraTaskImportBegan -lt $cameraTaskBegan -or $cameraTaskImportEnded -lt $cameraTaskImportBegan -or $cameraTaskImportEnded -gt $cameraTaskNow) {throw 'The report timestamps do not belong to this GUI command.'}
 if (-not $cameraTaskReport.success) {throw ('Camera import failed: '+$cameraTaskReport.error)}
 if ($cameraTaskReport.editor_pid -ne $ExistingEditorPid) {throw 'The report came from another UE process.'}
 if ($cameraTaskReport.import_script_sha256 -ne $cameraTaskScriptSha) {throw 'The report came from another import script version.'}
 if ($cameraTaskReport.target_root -ne '/Game/Yastars/Mesh/Camera' -or $cameraTaskReport.new_package_count -ne 7) {throw 'Unexpected camera import target or package count.'}
 if (-not $cameraTaskReport.run_id) {throw 'The report has no unique import run identifier.'}
 [ordered]@{
  success=$true;script='import_ue.py';execution_mode='existing_editor_console';
  run_id=$cameraTaskReport.run_id;editor_pid=$ExistingEditorPid;
  editor_process_created_utc=$cameraTaskCreatedUtc.ToString('o');editor_process_still_running=$true;
  editor_executable=$cameraTaskEditor.ExecutablePath;editor_command_line=$cameraTaskEditor.CommandLine;
  started_utc=$cameraTaskBegan.ToString('o');completed_utc=$cameraTaskNow.ToString('o');
  script_completed_utc=$cameraTaskReport.completed_utc;exit_code=$null;normal_zero_exit=$null;
  ue_editor_exit_requested=$false;fresh_console_report_verified=$true;report=$cameraTaskReportPath;
  script_sha256=$cameraTaskScriptSha;report_sha256=(Get-FileHash -LiteralPath $cameraTaskReportPath -Algorithm SHA256).Hash.ToLowerInvariant();
  target_root='/Game/Yastars/Mesh/Camera'
 } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $cameraTaskRoot 'ue_import_completion.json') -Encoding utf8
 Write-Output 'CAMERA_IMPORT_COMPLETED_IN_EXISTING_EDITOR'
 return
}
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
 throw 'Preserve the running UE editor. Save and close it before launching this exclusive import.'
}
$cameraTaskLog=Join-Path $cameraTaskRoot 'ue_import.log'
$cameraTaskCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
$cameraTaskPrivateDDC='D:/UE/Project/HorrorGame/Saved/CodexDDC/EnvelopeReplacement'
try {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$cameraTaskPrivateDDC,'Process')
 $cameraTaskStartedUtc=(Get-Date).ToUniversalTime()
 $cameraTaskProcess=Start-Process -FilePath 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe' -WindowStyle Hidden -ArgumentList @(
  '"D:\UE\Project\HorrorGame\HorrorGame.uproject"','/Engine/Maps/Entry',
  ('"-ExecutePythonScript='+$cameraTaskScript.Replace('\','/')+'"'),
  '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-RenderOffscreen',
  '-nosplash','-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding',
  '"-ExecCmds=Interchange.FeatureFlags.Import.FBX 0"',
  '-DDC=InstalledNoZenLocalFallback',
  ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path='+$cameraTaskPrivateDDC+',EnvPathOverride=UE-LocalDataCachePath)'),
  ('"-abslog='+$cameraTaskLog+'"')
 ) -PassThru -Wait
 $cameraTaskExit=$cameraTaskProcess.ExitCode
 [ordered]@{
  script='import_ue.py';execution_mode='exclusive_editor';pid=$cameraTaskProcess.Id;editor_pid=$cameraTaskProcess.Id;
  script_sha256=(Get-FileHash -LiteralPath $cameraTaskScript -Algorithm SHA256).Hash.ToLowerInvariant();
  started_utc=$cameraTaskStartedUtc.ToString('o');
  completed_utc=(Get-Date).ToUniversalTime().ToString('o');exit_code=$cameraTaskExit;
  normal_zero_exit=($cameraTaskExit -eq 0);report=$cameraTaskReportPath;
  temporary_engine_world='/Engine/Maps/Entry';private_ddc=$cameraTaskPrivateDDC;
  target_root='/Game/Yastars/Mesh/Camera'
 } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $cameraTaskRoot 'ue_import_completion.json') -Encoding utf8
 if ($cameraTaskExit -ne 0) {throw ('UE import helper exit '+$cameraTaskExit)}
 $cameraTaskReportFile=Get-Item -LiteralPath $cameraTaskReportPath
 if ($cameraTaskReportFile.LastWriteTimeUtc -lt $cameraTaskStartedUtc) {
  throw 'No fresh import report; Python may not have executed.'
 }
 $cameraTaskReport=Get-Content -LiteralPath $cameraTaskReportPath -Raw | ConvertFrom-Json
 if (-not $cameraTaskReport.success) {throw ('Camera import failed: '+$cameraTaskReport.error)}
 if ($cameraTaskReport.new_package_count -ne 7) {throw 'Camera import package count did not match 7.'}
 Write-Output 'CAMERA_IMPORT_COMPLETED_NORMAL_ZERO'
} finally {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$cameraTaskCache,'Process')
}
