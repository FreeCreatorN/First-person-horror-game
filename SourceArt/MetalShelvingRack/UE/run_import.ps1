param([switch]$VerifyExisting)
$ErrorActionPreference = 'Stop'
$rackRunnerDir = $PSScriptRoot
$rackProject = (Resolve-Path (Join-Path $rackRunnerDir '..\..\..')).Path
$rackProjectFile = Join-Path $rackProject 'HorrorGame.uproject'
$rackEditor = 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
$rackPython = Join-Path $rackProject 'Tools\CLI-Anything\venv\Scripts\python.exe'
$rackScript = Join-Path $rackRunnerDir 'import_ue.py'
$rackManifest = Join-Path $rackRunnerDir '..\Exports\export_report.json'
$rackBaseline = Join-Path $rackRunnerDir 'protected_content_sha256.json'
$rackPasses = @()
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) { throw 'The current Unreal editor must be preserved. Save and close it before this import.' }
if ($VerifyExisting) {
    $rackExistingReport = Get-Content -LiteralPath (Join-Path $rackRunnerDir 'ue_import_report.json') -Raw | ConvertFrom-Json
    if (-not $rackExistingReport.success) { throw 'Cannot verify an incomplete import' }
    $rackRunId = $rackExistingReport.run_id
    $rackPriorCompletion = Get-Content -LiteralPath (Join-Path $rackRunnerDir 'completion.json') -Raw | ConvertFrom-Json
    $rackPasses = @($rackPriorCompletion.runs | Where-Object { $_.mode -eq 'import' })
    if ($rackPasses.Count -ne 1 -or -not $rackPasses[0].normal_zero_exit) { throw 'Missing completed import pass' }
} else {
    & $rackPython (Join-Path $rackRunnerDir 'prepare_import.py')
    if ($LASTEXITCODE -ne 0) { throw 'Read-only export and destination checks failed' }
    $rackRunId = [Guid]::NewGuid().ToString()
}
$rackScriptSha = (Get-FileHash -LiteralPath $rackScript -Algorithm SHA256).Hash.ToLowerInvariant()
$rackManifestSha = (Get-FileHash -LiteralPath $rackManifest -Algorithm SHA256).Hash.ToLowerInvariant()
$rackBaselineSha = (Get-FileHash -LiteralPath $rackBaseline -Algorithm SHA256).Hash.ToLowerInvariant()
$rackDDC = (Join-Path $rackProject 'Saved\CodexDDC\EnvelopeReplacement').Replace('\','/')
$rackEnvironment = @{
    'UE-LocalDataCachePath' = $rackDDC
    RACK_UE_RUN_ID = $rackRunId
    RACK_UE_MANIFEST_SHA = $rackManifestSha
    RACK_UE_BASELINE_SHA = $rackBaselineSha
    RACK_UE_VERIFY_ONLY = '0'
}
$rackRestore = @{}
$rackCompletion = [ordered]@{ success=$false; run_id=$rackRunId; target_root='/Game/Yastars/Mesh/MetalShelvingRack'; script_sha256=$rackScriptSha; manifest_sha256=$rackManifestSha; baseline_sha256=$rackBaselineSha; started_utc=(Get-Date).ToUniversalTime().ToString('o'); runs=$rackPasses }

function Invoke-RackPass([string]$Mode) {
    if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) { throw 'An Unreal editor is now running. Keep it open and stop this helper.' }
    $rackReport = Join-Path $rackRunnerDir ('ue_' + $Mode + '_report.json')
    $rackLog = Join-Path $rackRunnerDir ('ue_' + $Mode + '.log')
    [Environment]::SetEnvironmentVariable('RACK_UE_VERIFY_ONLY', $(if ($Mode -eq 'reload') { '1' } else { '0' }), 'Process')
    $rackStarted = (Get-Date).ToUniversalTime()
    $rackArgs = @(('"' + $rackProjectFile + '"'), '/Engine/Maps/Entry',
        ('"-ExecutePythonScript=' + $rackScript.Replace('\','/') + '"'),
        '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities', '-unattended', '-nosound', '-nosplash', '-nop4',
        '-NOINI', '-NoAutoSave', '-nocef', '-NoLiveCoding', '-DDC=InstalledNoZenLocalFallback',
        ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=' + $rackDDC + ',EnvPathOverride=UE-LocalDataCachePath)'),
        ('"-abslog=' + $rackLog + '"'))
    $rackArgs += $(if ($Mode -eq 'reload') { '-NullRHI' } else { '-RenderOffscreen' })
    $rackProcess = Start-Process -FilePath $rackEditor -WindowStyle Hidden -ArgumentList $rackArgs -PassThru -Wait
    if ($rackProcess.ExitCode -ne 0) { throw ('UE ' + $Mode + ' exited with code ' + $rackProcess.ExitCode) }
    if ((Get-Item -LiteralPath $rackReport).LastWriteTimeUtc -lt $rackStarted) { throw ('Missing fresh report ' + $rackReport) }
    $rackResult = Get-Content -LiteralPath $rackReport -Raw | ConvertFrom-Json
    if (-not $rackResult.success) { throw ('UE ' + $Mode + ' failed: ' + $rackResult.error) }
    if ($rackResult.mode -ne $Mode -or $rackResult.editor_pid -ne $rackProcess.Id -or $rackResult.run_id -ne $rackRunId -or $rackResult.script_sha256 -ne $rackScriptSha -or $rackResult.manifest_sha256 -ne $rackManifestSha -or $rackResult.baseline_sha256 -ne $rackBaselineSha) {
        throw ('Report belongs to another UE process or source version: ' + $rackReport)
    }
    $rackErrors = @(Select-String -LiteralPath $rackLog -Pattern 'Failed to compile Material.*MetalShelvingRack|LogShaderCompilers: Error:|SHELVING_RACK_IMPORT_ERROR|Fatal error!')
    if ($rackErrors.Count) { throw ('Material, import, or fatal engine error. Check ' + $rackLog) }
    return [ordered]@{ mode=$Mode; editor_pid=$rackProcess.Id; normal_zero_exit=$true; exit_code=0; started_utc=$rackStarted.ToString('o'); completed_utc=(Get-Date).ToUniversalTime().ToString('o'); report=$rackReport; report_sha256=(Get-FileHash -LiteralPath $rackReport -Algorithm SHA256).Hash.ToLowerInvariant() }
}

try {
    foreach ($rackKey in $rackEnvironment.Keys) {
        $rackRestore[$rackKey] = [Environment]::GetEnvironmentVariable($rackKey, 'Process')
        [Environment]::SetEnvironmentVariable($rackKey, $rackEnvironment[$rackKey], 'Process')
    }
    if (-not $VerifyExisting) {
        $rackCompletion.runs += Invoke-RackPass 'import'
        $rackCompletion | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $rackRunnerDir 'completion.json') -Encoding utf8
    }
    $rackCompletion.runs += Invoke-RackPass 'reload'
    if ($rackCompletion.runs[0].editor_pid -eq $rackCompletion.runs[1].editor_pid) { throw 'UE did not launch a fresh readback process' }
    $rackCompletion.success = $true
} catch {
    $rackCompletion.error = $_.Exception.Message
    throw
} finally {
    $rackCompletion.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
    $rackCompletion | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $rackRunnerDir 'completion.json') -Encoding utf8
    foreach ($rackKey in $rackRestore.Keys) { [Environment]::SetEnvironmentVariable($rackKey, $rackRestore[$rackKey], 'Process') }
}

& $rackPython (Join-Path $rackRunnerDir 'verify_final.py')
if ($LASTEXITCODE -ne 0) { throw 'Final shelf verification failed' }
