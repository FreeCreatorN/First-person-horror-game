param()
$ErrorActionPreference='Stop'
$cameraSplitRoot='D:\UE\Project\HorrorGame\SourceArt\Camera\ShutterSplit'
$cameraSplitScript=Join-Path $cameraSplitRoot 'update_ue.py'
$cameraSplitReportPath=Join-Path $cameraSplitRoot 'update_ue_report.json'
$cameraSplitCompletionPath=Join-Path $cameraSplitRoot 'update_ue_completion.json'
if (-not (Test-Path -LiteralPath $cameraSplitScript -PathType Leaf)) {throw 'Missing camera shutter update script.'}
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
 throw 'Preserve the running UE editor. Save and close it before this exclusive camera update.'
}
$cameraSplitScriptSha=(Get-FileHash -LiteralPath $cameraSplitScript -Algorithm SHA256).Hash.ToLowerInvariant()
$cameraSplitCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
$cameraSplitOldRunId=[Environment]::GetEnvironmentVariable('CAMERA_SHUTTER_UPDATE_RUN_ID','Process')
$cameraSplitPrivateDDC='D:/UE/Project/HorrorGame/Saved/CodexDDC/EnvelopeReplacement'
$cameraSplitRunId=[Guid]::NewGuid().ToString()
$cameraSplitStartedUtc=(Get-Date).ToUniversalTime()
$cameraSplitCompletion=[ordered]@{
 success=$false;script='update_ue.py';execution_mode='exclusive_editor';
 run_id=$cameraSplitRunId;script_sha256=$cameraSplitScriptSha;
 started_utc=$cameraSplitStartedUtc.ToString('o');target_root='/Game/Yastars/Mesh/Camera';
 report=$cameraSplitReportPath;temporary_engine_world='/Engine/Maps/Entry';
 private_ddc=$cameraSplitPrivateDDC;normal_zero_exit=$false
}
try {
 foreach ($cameraSplitRequired in @('split_report.json','ue_before_manifest.json','protected_content_sha256.json')) {
  if (-not (Test-Path -LiteralPath (Join-Path $cameraSplitRoot $cameraSplitRequired) -PathType Leaf)) {throw ('Missing '+$cameraSplitRequired)}
 }
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$cameraSplitPrivateDDC,'Process')
 [Environment]::SetEnvironmentVariable('CAMERA_SHUTTER_UPDATE_RUN_ID',$cameraSplitRunId,'Process')
 $cameraSplitProcess=Start-Process -FilePath 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe' -WindowStyle Hidden -ArgumentList @(
  '"D:\UE\Project\HorrorGame\HorrorGame.uproject"','/Engine/Maps/Entry',
  ('"-ExecutePythonScript='+$cameraSplitScript.Replace('\','/')+'"'),
  '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-RenderOffscreen',
  '-nosplash','-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding',
  '"-ExecCmds=Interchange.FeatureFlags.Import.FBX 0"',
  '-DDC=InstalledNoZenLocalFallback',
  ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path='+$cameraSplitPrivateDDC+',EnvPathOverride=UE-LocalDataCachePath)'),
  ('"-abslog='+(Join-Path $cameraSplitRoot 'ue_update.log')+'"')
 ) -PassThru -Wait
 $cameraSplitCompletion.pid=$cameraSplitProcess.Id
 $cameraSplitCompletion.editor_pid=$cameraSplitProcess.Id
 $cameraSplitCompletion.exit_code=$cameraSplitProcess.ExitCode
 $cameraSplitCompletion.normal_zero_exit=($cameraSplitProcess.ExitCode -eq 0)
 if (-not $cameraSplitCompletion.normal_zero_exit) {throw ('UE camera update exit '+$cameraSplitProcess.ExitCode)}
 if ((Get-FileHash -LiteralPath $cameraSplitScript -Algorithm SHA256).Hash.ToLowerInvariant() -ne $cameraSplitScriptSha) {throw 'Update script changed during execution.'}
 $cameraSplitReportFile=Get-Item -LiteralPath $cameraSplitReportPath
 if ($cameraSplitReportFile.LastWriteTimeUtc -lt $cameraSplitStartedUtc) {throw 'No fresh camera update report.'}
 $cameraSplitReport=Get-Content -LiteralPath $cameraSplitReportPath -Raw | ConvertFrom-Json
 if (-not $cameraSplitReport.success) {throw ('Camera update failed: '+$cameraSplitReport.error)}
 if ($cameraSplitReport.run_id -ne $cameraSplitRunId -or $cameraSplitReport.editor_pid -ne $cameraSplitProcess.Id) {throw 'Camera report belongs to a different run.'}
 if ($cameraSplitReport.update_script_sha256 -ne $cameraSplitScriptSha) {throw 'Camera report came from a different script.'}
 if ($cameraSplitReport.target_root -ne '/Game/Yastars/Mesh/Camera' -or $cameraSplitReport.package_count_after -ne 8) {throw 'Unexpected camera update target or package count.'}
 $cameraSplitReportBegin=([DateTimeOffset]::Parse($cameraSplitReport.started_utc)).UtcDateTime
 $cameraSplitReportEnd=([DateTimeOffset]::Parse($cameraSplitReport.completed_utc)).UtcDateTime
 if ($cameraSplitReportBegin -lt $cameraSplitStartedUtc -or $cameraSplitReportEnd -lt $cameraSplitReportBegin -or $cameraSplitReportEnd -gt (Get-Date).ToUniversalTime()) {throw 'Camera update report timestamps do not match this run.'}
 $cameraSplitCompletion.report_sha256=(Get-FileHash -LiteralPath $cameraSplitReportPath -Algorithm SHA256).Hash.ToLowerInvariant()
 $cameraSplitCompletion.script_completed_utc=$cameraSplitReport.completed_utc
 $cameraSplitCompletion.success=$true
 Write-Output 'CAMERA_SHUTTER_UPDATE_COMPLETED_NORMAL_ZERO'
} catch {
 $cameraSplitCompletion.error=$_.Exception.Message
 throw
} finally {
 $cameraSplitCompletion.completed_utc=(Get-Date).ToUniversalTime().ToString('o')
 $cameraSplitCompletion | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $cameraSplitCompletionPath -Encoding utf8
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$cameraSplitCache,'Process')
 [Environment]::SetEnvironmentVariable('CAMERA_SHUTTER_UPDATE_RUN_ID',$cameraSplitOldRunId,'Process')
}
