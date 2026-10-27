param(
 [ValidatePattern('^[A-Za-z0-9_]+\.py$')]
 [string]$Script='inspect_legacy.py',
 [ValidatePattern('^([A-Za-z0-9_]+\.json)?$')]
 [string]$ReportFile=''
)

$ErrorActionPreference='Stop'
$envelopeTaskRoot='D:\UE\Project\HorrorGame\SourceArt\Envelope\Replacement'
$envelopeTaskScript=Join-Path $envelopeTaskRoot $Script
if (-not (Test-Path -LiteralPath $envelopeTaskScript -PathType Leaf)) {throw ('Missing script: '+$envelopeTaskScript)}
if (-not $ReportFile) {
 switch ($Script) {
  'inspect_legacy.py' {$ReportFile='legacy_inspection_report.json'}
  'import_set.py' {$ReportFile='ue_import_report.json'}
  default {throw 'Pass -ReportFile for a script without a known report name.'}
 }
}
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
 throw 'Preserve the running editor; only the parent may launch this task as the exclusive UE writer.'
}
$envelopeTaskStem=[IO.Path]::GetFileNameWithoutExtension($Script)
$envelopeTaskLog=Join-Path $envelopeTaskRoot ($envelopeTaskStem+'_ue.log')
$envelopeTaskReportPath=Join-Path $envelopeTaskRoot $ReportFile
$envelopeTaskCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
$envelopeTaskPrivateDDC='D:/UE/Project/HorrorGame/Saved/CodexDDC/EnvelopeReplacement'
try {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$envelopeTaskPrivateDDC,'Process')
 $envelopeTaskStartedUtc=(Get-Date).ToUniversalTime()
 $envelopeTaskStarted=$envelopeTaskStartedUtc.ToString('o')
 $envelopeTaskProcess=Start-Process -FilePath 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe' -WindowStyle Hidden -ArgumentList @(
  '"D:\UE\Project\HorrorGame\HorrorGame.uproject"','/Engine/Maps/Entry',
  ('"-ExecutePythonScript='+$envelopeTaskScript.Replace('\','/')+'"'),
  '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-RenderOffscreen',
  '-nosplash','-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding',
  '"-ExecCmds=Interchange.FeatureFlags.Import.FBX 0"',
  '-DDC=InstalledNoZenLocalFallback',
  ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path='+$envelopeTaskPrivateDDC+',EnvPathOverride=UE-LocalDataCachePath)'),
  ('"-abslog='+$envelopeTaskLog+'"')
 ) -PassThru -Wait
 $envelopeTaskExit=$envelopeTaskProcess.ExitCode
 [ordered]@{
  script=$Script;pid=$envelopeTaskProcess.Id;started_utc=$envelopeTaskStarted;
  completed_utc=(Get-Date).ToUniversalTime().ToString('o');exit_code=$envelopeTaskExit;
  normal_zero_exit=($envelopeTaskExit -eq 0);report=$envelopeTaskReportPath;
  temporary_engine_world='/Engine/Maps/Entry';private_ddc=$envelopeTaskPrivateDDC
 } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $envelopeTaskRoot ($envelopeTaskStem+'_completion.json')) -Encoding utf8
 if ($envelopeTaskExit -ne 0) {throw ('UE helper exit '+$envelopeTaskExit)}
 $envelopeTaskReportFile=Get-Item -LiteralPath $envelopeTaskReportPath
 if ($envelopeTaskReportFile.LastWriteTimeUtc -lt $envelopeTaskStartedUtc) {
  throw 'No fresh task report; Python may not have executed.'
 }
 $envelopeTaskReport=Get-Content -LiteralPath $envelopeTaskReportPath -Raw | ConvertFrom-Json
 if (-not $envelopeTaskReport.success) {throw ($Script+' failed: '+$envelopeTaskReport.error)}
 if ($envelopeTaskReport.PSObject.Properties.Name -contains 'deletion_gate_passed') {
  Write-Output ('ENVELOPE_DELETION_GATE_PASSED='+$envelopeTaskReport.deletion_gate_passed)
 }
 Write-Output ('ENVELOPE_TASK_COMPLETED_NORMAL_ZERO '+$Script)
} finally {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$envelopeTaskCache,'Process')
}
