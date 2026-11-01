$ErrorActionPreference = 'Stop'
$notebookNaturalRoot = 'D:\UE\Project\HorrorGame\SourceArt\Notebook\NaturalFlip\UE'
$notebookNaturalScript = Join-Path $notebookNaturalRoot 'update_ue.py'
$notebookNaturalPlan = Join-Path $notebookNaturalRoot 'update_plan.json'
$notebookNaturalPython = 'D:\UE\Project\HorrorGame\Tools\CLI-Anything\venv\Scripts\python.exe'
$notebookNaturalEditor = 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) { throw 'Preserve the running UE editor; this update requires it to be saved and closed.' }
& $notebookNaturalPython (Join-Path $notebookNaturalRoot 'prepare_update.py')
if ($LASTEXITCODE -ne 0) { throw 'The read-only preflight found an unexpected change; no UE update was started.' }
$notebookNaturalScriptSha = (Get-FileHash -LiteralPath $notebookNaturalScript -Algorithm SHA256).Hash.ToLowerInvariant()
$notebookNaturalPlanSha = (Get-FileHash -LiteralPath $notebookNaturalPlan -Algorithm SHA256).Hash.ToLowerInvariant()
$notebookNaturalRunId = [Guid]::NewGuid().ToString()
$notebookNaturalCacheBefore = [Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
$notebookNaturalRunBefore = [Environment]::GetEnvironmentVariable('NOTEBOOK_NATURAL_RUN_ID','Process')
$notebookNaturalModeBefore = [Environment]::GetEnvironmentVariable('NOTEBOOK_NATURAL_VERIFY_ONLY','Process')
$notebookNaturalDDC = 'D:/UE/Project/HorrorGame/Saved/CodexDDC/EnvelopeReplacement'
$notebookNaturalCompletion = [ordered]@{ success=$false; run_id=$notebookNaturalRunId; target_root='/Game/Yastars/Mesh/Notebook'; script_sha256=$notebookNaturalScriptSha; plan_sha256=$notebookNaturalPlanSha; started_utc=(Get-Date).ToUniversalTime().ToString('o'); runs=@() }

function Invoke-NotebookNaturalPass([bool]$ReadOnly) {
    if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) { throw 'A UE editor is running; preserve it and stop this helper.' }
    $notebookPassLabel = if ($ReadOnly) { 'reload' } else { 'update' }
    $notebookPassReport = Join-Path $notebookNaturalRoot $(if ($ReadOnly) { 'ue_reload_report.json' } else { 'update_ue_report.json' })
    $notebookPassLog = Join-Path $notebookNaturalRoot ($notebookPassLabel + '.log')
    $notebookPassStarted = (Get-Date).ToUniversalTime()
    [Environment]::SetEnvironmentVariable('NOTEBOOK_NATURAL_VERIFY_ONLY',$(if ($ReadOnly) { '1' } else { '0' }),'Process')
    $notebookPassArgs = @('"D:\UE\Project\HorrorGame\HorrorGame.uproject"','/Engine/Maps/Entry',
        ('"-ExecutePythonScript=' + $notebookNaturalScript.Replace('\','/') + '"'),
        '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-nosound','-nosplash',
        '-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding','-DDC=InstalledNoZenLocalFallback',
        ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=' + $notebookNaturalDDC + ',EnvPathOverride=UE-LocalDataCachePath)'),
        ('"-abslog=' + $notebookPassLog + '"'))
    $notebookPassArgs += $(if ($ReadOnly) { '-NullRHI' } else { '-RenderOffscreen' })
    $notebookPassProcess = Start-Process -FilePath $notebookNaturalEditor -WindowStyle Hidden -ArgumentList $notebookPassArgs -PassThru -Wait
    if ($notebookPassProcess.ExitCode -ne 0) { throw ($notebookPassLabel + ' UE helper exited with code ' + $notebookPassProcess.ExitCode) }
    if ((Get-FileHash -LiteralPath $notebookNaturalScript -Algorithm SHA256).Hash.ToLowerInvariant() -ne $notebookNaturalScriptSha -or
        (Get-FileHash -LiteralPath $notebookNaturalPlan -Algorithm SHA256).Hash.ToLowerInvariant() -ne $notebookNaturalPlanSha) { throw 'Update script or plan changed while UE was running.' }
    if ((Get-Item -LiteralPath $notebookPassReport).LastWriteTimeUtc -lt $notebookPassStarted) { throw 'No fresh UE report exists.' }
    $notebookPassData = Get-Content -LiteralPath $notebookPassReport -Raw | ConvertFrom-Json
    if (-not $notebookPassData.success) { throw ($notebookPassLabel + ' failed: ' + $notebookPassData.error) }
    if ($notebookPassData.editor_pid -ne $notebookPassProcess.Id -or $notebookPassData.run_id -ne $notebookNaturalRunId -or
        $notebookPassData.script_sha256 -ne $notebookNaturalScriptSha -or $notebookPassData.plan_sha256 -ne $notebookNaturalPlanSha) { throw 'Report belongs to another run or source version.' }
    $notebookPassErrors = @(Select-String -LiteralPath $notebookPassLog -Pattern 'Failed to compile Material[^\r\n]*Notebook|LogShaderCompilers: Error:|NOTEBOOK_NATURAL_UPDATE_ERROR|Fatal error!')
    if ($notebookPassErrors.Count) { throw 'The UE helper logged an update, shader or fatal error.' }
    return [ordered]@{ mode=$notebookPassData.mode; editor_pid=$notebookPassProcess.Id; normal_zero_exit=$true; exit_code=0; started_utc=$notebookPassStarted.ToString('o'); completed_utc=(Get-Date).ToUniversalTime().ToString('o'); report=$notebookPassReport; report_sha256=(Get-FileHash -LiteralPath $notebookPassReport -Algorithm SHA256).Hash.ToLowerInvariant(); log_error_count=0 }
}

try {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$notebookNaturalDDC,'Process')
    [Environment]::SetEnvironmentVariable('NOTEBOOK_NATURAL_RUN_ID',$notebookNaturalRunId,'Process')
    $notebookNaturalCompletion.runs += Invoke-NotebookNaturalPass $false
    $notebookNaturalCompletion.runs += Invoke-NotebookNaturalPass $true
    if ($notebookNaturalCompletion.runs[0].editor_pid -eq $notebookNaturalCompletion.runs[1].editor_pid) { throw 'The persistence pass did not use a fresh editor process.' }
    $notebookNaturalCompletion.success = $true
} catch {
    $notebookNaturalCompletion.error = $_.Exception.Message
    throw
} finally {
    $notebookNaturalCompletion.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
    $notebookNaturalCompletion | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $notebookNaturalRoot 'completion.json') -Encoding utf8
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$notebookNaturalCacheBefore,'Process')
    [Environment]::SetEnvironmentVariable('NOTEBOOK_NATURAL_RUN_ID',$notebookNaturalRunBefore,'Process')
    [Environment]::SetEnvironmentVariable('NOTEBOOK_NATURAL_VERIFY_ONLY',$notebookNaturalModeBefore,'Process')
}
& $notebookNaturalPython (Join-Path $notebookNaturalRoot 'verify_final.py')
if ($LASTEXITCODE -ne 0) { throw 'Final Notebook update verification failed.' }
Write-Output 'NOTEBOOK_NATURAL_UPDATE_NORMAL_ZERO'
