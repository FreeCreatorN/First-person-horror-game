$ErrorActionPreference='Stop'
$penTaskRoot='D:\UE\Project\HorrorGame\SourceArt\Pen'
$penTaskScript=Join-Path $penTaskRoot 'import_ue.py'
if (-not (Test-Path -LiteralPath $penTaskScript -PathType Leaf)) {throw ('Missing script: '+$penTaskScript)}
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
 throw 'Preserve the running UE editor. Save and close it before launching this exclusive import.'
}
$penTaskFailureBackup=$null
$penTaskPreviousReport=Join-Path $penTaskRoot 'ue_import_report.json'
if (Test-Path -LiteralPath $penTaskPreviousReport -PathType Leaf) {
 $penTaskPrevious=Get-Content -LiteralPath $penTaskPreviousReport -Raw | ConvertFrom-Json
 if (-not $penTaskPrevious.success) {
  if ($penTaskPrevious.target_root -ne '/Game/Yastars/Mesh/Pen') {throw 'Unexpected prior failure report; preserve it for review.'}
  $penTaskFailureBackup=Join-Path $penTaskRoot 'FailedImportBeforeFix'
  $penTaskStoredFailure=Join-Path $penTaskFailureBackup 'ue_import_report.json'
  if ((Test-Path -LiteralPath $penTaskStoredFailure) -and ((Get-FileHash -LiteralPath $penTaskStoredFailure -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $penTaskPreviousReport -Algorithm SHA256).Hash)) {
   $penTaskFailureBackup=Join-Path $penTaskFailureBackup ('Attempt_'+(Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_ffff'))
  }
  [IO.Directory]::CreateDirectory($penTaskFailureBackup) | Out-Null
  foreach ($penTaskArtifact in @('ue_import_report.json','ue_import_completion.json','ue_import.log')) {
   $penTaskArtifactSource=Join-Path $penTaskRoot $penTaskArtifact
   $penTaskArtifactBackup=Join-Path $penTaskFailureBackup $penTaskArtifact
   if (Test-Path -LiteralPath $penTaskArtifactSource -PathType Leaf) {
    if (-not (Test-Path -LiteralPath $penTaskArtifactBackup)) {Copy-Item -LiteralPath $penTaskArtifactSource -Destination $penTaskArtifactBackup}
    if ((Get-FileHash -LiteralPath $penTaskArtifactSource -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $penTaskArtifactBackup -Algorithm SHA256).Hash) {throw 'Prior failure backup differs; preserve both before retrying.'}
   }
  }
 }
}
$penTaskLog=Join-Path $penTaskRoot 'ue_import.log'
$penTaskReportPath=Join-Path $penTaskRoot 'ue_import_report.json'
$penTaskCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
$penTaskPrivateDDC='D:/UE/Project/HorrorGame/Saved/CodexDDC/EnvelopeReplacement'
try {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$penTaskPrivateDDC,'Process')
 $penTaskStartedUtc=(Get-Date).ToUniversalTime()
 $penTaskProcess=Start-Process -FilePath 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe' -WindowStyle Hidden -ArgumentList @(
  '"D:\UE\Project\HorrorGame\HorrorGame.uproject"','/Engine/Maps/Entry',
  ('"-ExecutePythonScript='+$penTaskScript.Replace('\','/')+'"'),
  '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-RenderOffscreen',
  '-nosplash','-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding',
  '"-ExecCmds=Interchange.FeatureFlags.Import.FBX 0"',
  '-DDC=InstalledNoZenLocalFallback',
  ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path='+$penTaskPrivateDDC+',EnvPathOverride=UE-LocalDataCachePath)'),
  ('"-abslog='+$penTaskLog+'"')
 ) -PassThru -Wait
 $penTaskExit=$penTaskProcess.ExitCode
 [ordered]@{
  script='import_ue.py';pid=$penTaskProcess.Id;started_utc=$penTaskStartedUtc.ToString('o');
  completed_utc=(Get-Date).ToUniversalTime().ToString('o');exit_code=$penTaskExit;
  normal_zero_exit=($penTaskExit -eq 0);report=$penTaskReportPath;
  temporary_engine_world='/Engine/Maps/Entry';private_ddc=$penTaskPrivateDDC;
  target_root='/Game/Yastars/Mesh/Pen'
  previous_failure_backup=$penTaskFailureBackup
 } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $penTaskRoot 'ue_import_completion.json') -Encoding utf8
 if ($penTaskExit -ne 0) {throw ('UE import helper exit '+$penTaskExit)}
 $penTaskReportFile=Get-Item -LiteralPath $penTaskReportPath
 if ($penTaskReportFile.LastWriteTimeUtc -lt $penTaskStartedUtc) {
  throw 'No fresh import report; Python may not have executed.'
 }
 $penTaskReport=Get-Content -LiteralPath $penTaskReportPath -Raw | ConvertFrom-Json
 if (-not $penTaskReport.success) {throw ('Pen import failed: '+$penTaskReport.error)}
 if ($penTaskReport.new_package_count -ne 6) {throw 'Pen import package count did not match 6.'}
 Write-Output 'PEN_IMPORT_COMPLETED_NORMAL_ZERO'
} finally {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$penTaskCache,'Process')
}
