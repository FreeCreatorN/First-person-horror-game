$ErrorActionPreference='Stop'
$taskWork='D:\UE\Project\HorrorGame\Saved\CodexOutputs\OldTownHotelNaming_20261017'
$taskPython='C:\Users\aa131\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$taskDone=Get-Content -LiteralPath (Join-Path $taskWork 'RefreshedAudit1.Completion.json') -Raw | ConvertFrom-Json
if (-not $taskDone.normal_zero_exit) {throw 'Full refreshed scene must pass first'}
foreach($taskArtifact in @('RefreshedReferences.json','SupplementalCleanupResult.json','CleanAudit.json','CleanReferences.json','FinalReview.json')) {
 if (Test-Path -LiteralPath (Join-Path $taskWork $taskArtifact)) {throw ('Resume existing milestone explicitly: '+$taskArtifact)}
}
try {
 $env:HOTEL_REF_MODE='Refreshed'
 & 'D:\UE\Project\HorrorGame\Scripts\RunOldTownHotelNamingTask.ps1' -Script 'D:\UE\Project\HorrorGame\Scripts\InspectHotelNamingReferences.py' -LogName RefreshedReferences1
 Remove-Item Env:HOTEL_REF_MODE
 & $taskPython -X utf8 'D:\UE\Project\HorrorGame\Scripts\CleanupHotelStaleDoorsOffline.py'
 if ($LASTEXITCODE -ne 0) {throw 'Supplemental isolation failed'}
 $env:HOTEL_AUDIT_MODE='Clean'
 & 'D:\UE\Project\HorrorGame\Scripts\RunOldTownHotelNamingTask.ps1' -Script 'D:\UE\Project\HorrorGame\Scripts\AuditOldTownHotelNaming.py' -LogName CleanAudit1
 Remove-Item Env:HOTEL_AUDIT_MODE
 $env:HOTEL_REF_MODE='Clean'
 & 'D:\UE\Project\HorrorGame\Scripts\RunOldTownHotelNamingTask.ps1' -Script 'D:\UE\Project\HorrorGame\Scripts\InspectHotelNamingReferences.py' -LogName CleanReferences1
 Remove-Item Env:HOTEL_REF_MODE
 & $taskPython -X utf8 'D:\UE\Project\HorrorGame\Scripts\FinalizeHotelNaming.py'
 if ($LASTEXITCODE -ne 0) {throw 'Final proof failed'}
 & $taskPython -X utf8 'D:\UE\Project\HorrorGame\Scripts\WriteHotelNamingResult.py'
 if ($LASTEXITCODE -ne 0) {throw 'Handoff failed'}
 Write-Output 'HOTEL_NAMING_ALL_COMPLETE'
} finally {
 Remove-Item Env:HOTEL_REF_MODE -ErrorAction SilentlyContinue
 Remove-Item Env:HOTEL_AUDIT_MODE -ErrorAction SilentlyContinue
}
