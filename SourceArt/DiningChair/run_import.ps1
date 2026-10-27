$ErrorActionPreference='Stop'
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {throw 'Preserve the running editor; do not launch a second writer.'}
$chairSource='D:\UE\Project\HorrorGame\SourceArt\DiningChair'
$chairCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
try {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath','D:\UE\Project\HorrorGame\Saved\CodexDDC','Process')
 $chairStartedUtc=(Get-Date).ToUniversalTime()
 $chairStarted=$chairStartedUtc.ToString('o')
 $chairProcess=Start-Process -FilePath 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe' -WindowStyle Hidden -ArgumentList @(
  '"D:\UE\Project\HorrorGame\HorrorGame.uproject"','/Engine/Maps/Entry',
  '"-ExecutePythonScript=D:/UE/Project/HorrorGame/SourceArt/DiningChair/import_ue.py"',
  '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-RenderOffscreen',
  '-nosplash','-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding',
  '"-ExecCmds=Interchange.FeatureFlags.Import.FBX 0"',
  '-DDC=InstalledNoZenLocalFallback',
  '-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=D:/UE/Project/HorrorGame/Saved/CodexDDC,EnvPathOverride=UE-LocalDataCachePath)',
  '"-abslog=D:\UE\Project\HorrorGame\SourceArt\DiningChair\ue_auto_import.log"'
 ) -PassThru -Wait
 $chairExit=$chairProcess.ExitCode
 [ordered]@{pid=$chairProcess.Id;started_utc=$chairStarted;completed_utc=(Get-Date).ToUniversalTime().ToString('o');exit_code=$chairExit;normal_zero_exit=($chairExit -eq 0)} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $chairSource 'ue_import_completion.json') -Encoding utf8
 if ($chairExit -ne 0) {throw ('UE helper exit '+$chairExit)}
 $chairReportPath=Join-Path $chairSource 'ue_import_report.json'
 $chairReportFile=Get-Item -LiteralPath $chairReportPath
 if ($chairReportFile.LastWriteTimeUtc -lt $chairStartedUtc) {throw 'No fresh chair import report; Python may not have executed.'}
 $chairReport=Get-Content -LiteralPath $chairReportPath -Raw | ConvertFrom-Json
 if (-not $chairReport.success) {throw $chairReport.error}
 Write-Output 'DINING_CHAIR_IMPORT_COMPLETED_NORMAL_ZERO'
} finally {[Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$chairCache,'Process')}
