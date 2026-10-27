param(
    [string[]]$Cameras = @(),
    [ValidateSet('temporary', 'street_only')][string]$Lighting = 'temporary',
    [ValidateSet('lit', 'unlit')][string]$ViewMode = 'lit',
    [ValidateRange(1, 4)][int]$BatchSize = 4,
    [switch]$ForceRecapture,
    [string]$BuildReport = 'D:\UE\Project\HorrorGame\Saved\CodexOutputs\EnterableStreet_20261002\BuildReport.json',
    [string]$OutputDirectory = 'D:\UE\Project\HorrorGame\Saved\CodexOutputs\HotelOpenings_20261004'
)
# User-authorized Main editing continues in the separate GUI editor.
# Only newly launched, hidden capture helpers are managed. No process-name or
# user-editor cleanup is used; PID 24236 is explicitly outside this script.
$ErrorActionPreference = 'Stop'
$hotelProject = 'D:\UE\Project\HorrorGame'
$refinementLiveEditors=@(Get-Process -Name UnrealEditor-Cmd -ErrorAction SilentlyContinue | Where-Object { -not $_.HasExited })
if ($refinementLiveEditors.Count -ne 0) { throw 'Another commandlet is running; no capture helper launched.' }
$hotelOutputRoot = [System.IO.Path]::GetFullPath((Join-Path $hotelProject 'Saved\CodexOutputs')).TrimEnd('\', '/')
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { throw 'A capture output directory is required.' }
$hotelOutputInput = if ([System.IO.Path]::IsPathRooted($OutputDirectory)) { $OutputDirectory }
    else { Join-Path $hotelProject $OutputDirectory }
$hotelOutput = [System.IO.Path]::GetFullPath($hotelOutputInput).TrimEnd('\', '/')
if (-not $hotelOutput.StartsWith(($hotelOutputRoot + '\'), [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Capture output must stay below project Saved\CodexOutputs.'
}
# Existing junctions or symbolic links can escape an otherwise valid lexical
# path. Refuse them before creating or overwriting any capture files.
$hotelOutputAncestor = $hotelOutput
while ($true) {
    if (Test-Path -LiteralPath $hotelOutputAncestor) {
        $hotelOutputItem = Get-Item -LiteralPath $hotelOutputAncestor -Force
        if (($hotelOutputItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Capture output may not pass through a junction or symbolic link.'
        }
    }
    if ($hotelOutputAncestor.Equals($hotelProject, [System.StringComparison]::OrdinalIgnoreCase)) { break }
    $hotelOutputAncestor = [System.IO.Path]::GetDirectoryName($hotelOutputAncestor)
}
$hotelRenders = Join-Path $hotelOutput 'Renders'
$hotelCaptureScript = Join-Path $hotelProject 'Scripts\CaptureOldTownSoftGoodsViews.py'
$hotelEditor = 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
$hotelReport = Get-Content -LiteralPath $BuildReport -Raw | ConvertFrom-Json
$hotelLevel = $hotelReport.target_level
if ($hotelLevel -notmatch '^/Game/Yastar/Maps/Scenes/L_OldTown[A-Za-z0-9_]+$') { throw 'Unexpected hotel review map path.' }
$hotelMap = Join-Path $hotelProject ('Content/' + $hotelLevel.Substring(6) + '.umap')
$hotelMapHash = (Get-FileHash -LiteralPath $hotelMap -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hotelReport.map_sha256.ToLowerInvariant() -ne $hotelMapHash) {
    throw 'Hotel build report and persisted map hashes differ.'
}
if ($Cameras.Count -eq 0) { $Cameras = @($hotelReport.hotel_openings_review_cameras) }
if ($Cameras.Count -eq 0) { throw 'No hotel review cameras in the current build report.' }
if (@($Cameras | Select-Object -Unique).Count -ne $Cameras.Count) { throw 'Duplicate review camera labels.' }
foreach ($hotelCamera in $Cameras) {
    if ($hotelCamera -notmatch '^[A-Za-z0-9_]+$') { throw ('Unsafe camera label: ' + $hotelCamera) }
}
[void](New-Item -ItemType Directory -Path $hotelRenders -Force)
[void](New-Item -ItemType Directory -Path (Join-Path $hotelOutput 'Runs') -Force)
$hotelRunPrefix = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ') + '_' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$hotelResultsPath = Join-Path $hotelOutput 'CaptureRuns.json'
$hotelResults = @()
if (Test-Path -LiteralPath $hotelResultsPath) {
    $hotelResults = @(Get-Content -LiteralPath $hotelResultsPath -Raw | ConvertFrom-Json)
}

function Test-HotelCapture([string]$Camera, [datetime]$Since = [datetime]::MinValue,
                          [string]$RunId = '', [int]$OwnedPid = 0) {
    $capturePng = Join-Path $hotelRenders ($Camera + '.png')
    $captureMeta = Join-Path $hotelRenders ($Camera + '.json')
    if (-not (Test-Path -LiteralPath $capturePng) -or -not (Test-Path -LiteralPath $captureMeta)) { return $false }
    try {
        $captureMetadata = Get-Content -LiteralPath $captureMeta -Raw | ConvertFrom-Json
        $expectedAssetProperties = @($hotelReport.new_asset_sha256.PSObject.Properties)
        $capturedAssetProperties = @($captureMetadata.new_asset_sha256.PSObject.Properties)
        if ($expectedAssetProperties.Count -ne $capturedAssetProperties.Count -or
            $captureMetadata.appearance_assets_unchanged -ne $true) { return $false }
        foreach ($captureAsset in $expectedAssetProperties) {
            if ($captureMetadata.new_asset_sha256.PSObject.Properties[$captureAsset.Name].Value -ne $captureAsset.Value -or
                $captureMetadata.asset_sha256_after_cleanup.PSObject.Properties[$captureAsset.Name].Value -ne $captureAsset.Value) { return $false }
        }
        $captureImage = Get-Item -LiteralPath $capturePng
        $captureInfo = Get-Item -LiteralPath $captureMeta
        $captureHash = (Get-FileHash -LiteralPath $capturePng -Algorithm SHA256).Hash.ToLowerInvariant()
        if (($RunId -and $captureMetadata.run_id -ne $RunId) -or
            ($OwnedPid -and $captureMetadata.owned_editor_pid -ne $OwnedPid)) { return $false }
        return $captureMetadata.status -eq 'PASS' -and $captureMetadata.camera -eq $Camera -and
            $captureMetadata.map_sha256 -eq $hotelMapHash -and $captureMetadata.bytes -eq $captureImage.Length -and
            $captureMetadata.png_sha256 -eq $captureHash -and $captureImage.Length -gt 20000 -and
            $captureMetadata.lighting_mode -eq $Lighting -and $captureMetadata.view_mode_verified -eq $ViewMode -and
            $captureMetadata.temporary_lighting_cleanup_verified_zero -eq $true -and
            $captureMetadata.temporary_lighting_cleanup_remaining_count -eq 0 -and
            $captureMetadata.source -eq 'fresh_persisted_map_load' -and
            $captureMetadata.persisted_map_unchanged -eq $true -and $captureInfo.LastWriteTime -ge $Since -and
            $captureImage.LastWriteTime -ge $Since
    } catch { return $false }
}

$hotelPending = @()
foreach ($hotelCamera in $Cameras) {
    if (-not $ForceRecapture -and (Test-HotelCapture $hotelCamera)) {
        $hotelResults += [pscustomobject]@{camera=$hotelCamera; captured=$true; reused=$true; lighting_mode=$Lighting;
            view_mode=$ViewMode; map_sha256=$hotelMapHash; path=(Join-Path $hotelRenders ($hotelCamera + '.png'))}
        Write-Output ($hotelCamera + ': verified saved capture, lighting=' + $Lighting)
    } else { $hotelPending += $hotelCamera }
}
ConvertTo-Json -InputObject @($hotelResults) -Depth 8 | Set-Content -LiteralPath $hotelResultsPath -Encoding utf8
$hotelEnvNames = @('OTS_CAPTURE_LEVEL', 'OTS_CAPTURE_CAMERAS', 'OTS_CAPTURE_RUN_ID', 'OTS_CAPTURE_BUILD_REPORT',
                  'OTS_CAPTURE_OUTPUT', 'OTS_REVIEW_LIGHTING', 'OTS_REVIEW_VIEW_MODE', 'UE-LocalDataCachePath')
$hotelPreviousEnv = @{}
foreach ($hotelEnvName in $hotelEnvNames) {
    $hotelPreviousEnv[$hotelEnvName] = [Environment]::GetEnvironmentVariable($hotelEnvName, 'Process')
}
$hotelOwnedProcess = $null
try {
    for ($hotelOffset = 0; $hotelOffset -lt $hotelPending.Count; $hotelOffset += $BatchSize) {
        $hotelBatch = @($hotelPending[$hotelOffset..([Math]::Min($hotelOffset + $BatchSize - 1, $hotelPending.Count - 1))])
        $hotelBatchNumber = [int]($hotelOffset / $BatchSize) + 1
        $hotelRunId = $hotelRunPrefix + '_b' + $hotelBatchNumber.ToString('00')
        $hotelRunDir = Join-Path $hotelOutput ('Runs\' + $hotelRunId)
        $hotelArchive = Join-Path $hotelRunDir 'Renders'
        $hotelBefore = Join-Path $hotelRunDir 'BeforeRenders'
        [void](New-Item -ItemType Directory -Path $hotelRunDir -Force)
        [void](New-Item -ItemType Directory -Path $hotelArchive -Force)
        [void](New-Item -ItemType Directory -Path $hotelBefore -Force)
        foreach ($hotelCamera in $hotelBatch) {
            foreach ($hotelExtension in @('.png', '.json')) {
                $hotelOldCapture = Join-Path $hotelRenders ($hotelCamera + $hotelExtension)
                if (Test-Path -LiteralPath $hotelOldCapture) {
                    Copy-Item -LiteralPath $hotelOldCapture -Destination (Join-Path $hotelBefore ($hotelCamera + $hotelExtension))
                }
            }
        }
        [Environment]::SetEnvironmentVariable('OTS_CAPTURE_CAMERAS', ($hotelBatch -join ','), 'Process')
        [Environment]::SetEnvironmentVariable('OTS_CAPTURE_RUN_ID', $hotelRunId, 'Process')
        [Environment]::SetEnvironmentVariable('OTS_CAPTURE_BUILD_REPORT', $BuildReport, 'Process')
        [Environment]::SetEnvironmentVariable('OTS_CAPTURE_LEVEL', $hotelLevel, 'Process')
        [Environment]::SetEnvironmentVariable('OTS_CAPTURE_OUTPUT', $hotelOutput, 'Process')
        [Environment]::SetEnvironmentVariable('OTS_REVIEW_LIGHTING', $Lighting, 'Process')
        [Environment]::SetEnvironmentVariable('OTS_REVIEW_VIEW_MODE', $ViewMode, 'Process')
        [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath', (Join-Path $hotelProject 'Saved\CodexDDC'), 'Process')
        $hotelStart = Get-Date
        $hotelStdout = Join-Path $hotelRunDir 'Editor.stdout.log'
        $hotelStderr = Join-Path $hotelRunDir 'Editor.stderr.log'
        $hotelLog = Join-Path $hotelRunDir 'Editor.log'
        $hotelOwnedProcess = Start-Process -FilePath $hotelEditor -ArgumentList @(
            ('"' + (Join-Path $hotelProject 'HorrorGame.uproject') + '"'),
            $hotelLevel,
            ('-ExecutePythonScript="' + $hotelCaptureScript + '"'),
            '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities,GeometryScripting,MainHomeInteractive',
            '-ddc=InstalledNoZenLocalFallback', '-unattended', '-NoSound', '-NoSplash', '-nop4',
            # Capture helpers need no embedded browser. CEF initialization in
            # restricted sessions can fail its child-process/cache permissions.
            # Flush the editor log so a bounded shutdown has useful diagnostics.
            '-RenderOffscreen', '-NoAutoSave', '-NOINI', '-nocef', '-FORCELOGFLUSH',
            '-stdout', '-FullStdOutLogOutput', '-UTF8Output',
            ('-abslog="' + $hotelLog + '"')
        ) -WorkingDirectory $hotelProject -WindowStyle Hidden -RedirectStandardOutput $hotelStdout -RedirectStandardError $hotelStderr -PassThru
        if ($hotelOwnedProcess.Id -eq 24236) { throw 'User editor PID is excluded from helper ownership.' }
        $hotelOwnedPid = $hotelOwnedProcess.Id
        $hotelPidEvidence = [ordered]@{run_id=$hotelRunId; owned_editor_pid=$hotelOwnedPid;
            wrapper_pid=$PID; user_editor_pid_excluded=24236; launch_time_utc=$hotelStart.ToUniversalTime().ToString('o');
            lighting_mode=$Lighting; view_mode=$ViewMode; cameras=$hotelBatch; map_sha256=$hotelMapHash;
            output_directory=$hotelOutput;
            stdout=$hotelStdout; stderr=$hotelStderr; log=$hotelLog; window_style='Hidden';
            map_save_requested=$false; no_auto_save=$true; cleanup_only_owned_process=$true;
            embedded_browser_disabled=$true; force_log_flush=$true;
            shutdown_grace_seconds=20; helper_timeout_seconds=720}
        ConvertTo-Json -InputObject $hotelPidEvidence -Depth 8 | Set-Content -LiteralPath (Join-Path $hotelRunDir 'OwnedProcess.json') -Encoding utf8
        $hotelFinishedAt = $null
        $hotelForcedCleanup = $false
        $hotelCleanupReason = $null
        while (-not $hotelOwnedProcess.HasExited) {
            $hotelReady = $true
            foreach ($hotelCamera in $hotelBatch) {
                if (-not (Test-HotelCapture $hotelCamera $hotelStart $hotelRunId $hotelOwnedPid)) { $hotelReady = $false; break }
            }
            if ($hotelReady -and $null -eq $hotelFinishedAt) { $hotelFinishedAt = Get-Date }
            $hotelBatchSummary = Join-Path $hotelRunDir 'CaptureBatch.json'
            if ($null -eq $hotelFinishedAt -and (Test-Path -LiteralPath $hotelBatchSummary)) {
                try {
                    $hotelTerminal = Get-Content -LiteralPath $hotelBatchSummary -Raw | ConvertFrom-Json
                    if ($hotelTerminal.status -in @('PASS', 'FAIL') -and
                        $hotelTerminal.run_id -eq $hotelRunId -and
                        $hotelTerminal.owned_editor_pid -eq $hotelOwnedPid -and
                        (Get-Item -LiteralPath $hotelBatchSummary).LastWriteTime -ge $hotelStart) {
                        $hotelFinishedAt = Get-Date
                    }
                } catch { }
            }
            if (($null -ne $hotelFinishedAt -and ((Get-Date) - $hotelFinishedAt).TotalSeconds -gt 20) -or
                ((Get-Date) - $hotelStart).TotalSeconds -gt 720) {
                $hotelOwnedProcess.Refresh()
                if (-not $hotelOwnedProcess.HasExited) {
                    $hotelCleanupReason = if ($null -ne $hotelFinishedAt) { '20 seconds after terminal capture cleanup report' } else { 'owned helper capture timeout' }
                    $hotelOwnedProcess.Kill()
                    $hotelForcedCleanup = $true
                }
                break
            }
            [void]$hotelOwnedProcess.WaitForExit(1000)
        }
        [void]$hotelOwnedProcess.WaitForExit(10000)
        $hotelPidEvidence.exit_code = $hotelOwnedProcess.ExitCode
        $hotelPidEvidence.forced_cleanup = $hotelForcedCleanup
        $hotelPidEvidence.cleanup_reason = $hotelCleanupReason
        $hotelPidEvidence.helper_has_exited = $hotelOwnedProcess.HasExited
        $hotelPidEvidence.normal_exit = $hotelOwnedProcess.HasExited -and -not $hotelForcedCleanup -and
            $hotelOwnedProcess.ExitCode -eq 0
        $hotelPidEvidence.lifecycle_status = if ($hotelForcedCleanup) { 'FORCED_CLEANUP' }
            elseif ($hotelPidEvidence.normal_exit) { 'NORMAL_EXIT' } else { 'EXIT_ERROR' }
        $hotelShutdownPath = Join-Path $hotelRunDir 'ShutdownRequest.json'
        $hotelPidEvidence.shutdown_request = $null
        if (Test-Path -LiteralPath $hotelShutdownPath) {
            try {
                $hotelShutdown = Get-Content -LiteralPath $hotelShutdownPath -Raw | ConvertFrom-Json
                if ($hotelShutdown.run_id -eq $hotelRunId -and $hotelShutdown.owned_editor_pid -eq $hotelOwnedPid) {
                    $hotelPidEvidence.shutdown_request = $hotelShutdown
                }
            } catch { }
        }
        $hotelPidEvidence.end_time_utc = (Get-Date).ToUniversalTime().ToString('o')
        $hotelPidEvidence.map_sha256_after = (Get-FileHash -LiteralPath $hotelMap -Algorithm SHA256).Hash.ToLowerInvariant()
        $hotelPidEvidence.persisted_map_unchanged = $hotelPidEvidence.map_sha256_after -eq $hotelMapHash
        ConvertTo-Json -InputObject $hotelPidEvidence -Depth 8 | Set-Content -LiteralPath (Join-Path $hotelRunDir 'OwnedProcess.json') -Encoding utf8
        $hotelBatchPassed = $true
        foreach ($hotelCamera in $hotelBatch) {
            $hotelCaptured = (Test-HotelCapture $hotelCamera $hotelStart $hotelRunId $hotelOwnedPid) -and $hotelPidEvidence.persisted_map_unchanged
            $hotelPng = Join-Path $hotelRenders ($hotelCamera + '.png')
            foreach ($hotelExtension in @('.png', '.json')) {
                $hotelCapturePath = Join-Path $hotelRenders ($hotelCamera + $hotelExtension)
                if (Test-Path -LiteralPath $hotelCapturePath) {
                    Copy-Item -LiteralPath $hotelCapturePath -Destination (Join-Path $hotelArchive ($hotelCamera + $hotelExtension))
                }
            }
            $hotelResults += [pscustomobject]@{camera=$hotelCamera; captured=$hotelCaptured; reused=$false;
                lighting_mode=$Lighting; view_mode=$ViewMode; map_sha256=$hotelMapHash; owned_editor_pid=$hotelOwnedPid;
                run_id=$hotelRunId; exit_code=$hotelOwnedProcess.ExitCode; forced_cleanup=$hotelForcedCleanup;
                normal_exit=$hotelPidEvidence.normal_exit; lifecycle_status=$hotelPidEvidence.lifecycle_status;
                new_asset_sha256=$hotelReport.new_asset_sha256;
                path=$hotelPng; archive=(Join-Path $hotelArchive ($hotelCamera + '.png'))}
            Write-Output ($hotelCamera + ': captured=' + $hotelCaptured + ' lighting=' + $Lighting + ' helper_exit=' + $hotelOwnedProcess.ExitCode)
            if (-not $hotelCaptured) { $hotelBatchPassed = $false }
        }
        ConvertTo-Json -InputObject @($hotelResults) -Depth 8 | Set-Content -LiteralPath $hotelResultsPath -Encoding utf8
        $hotelOwnedProcess.Dispose()
        $hotelOwnedProcess = $null
        if (-not $hotelBatchPassed) { throw ('Hotel capture batch failed: ' + ($hotelBatch -join ', ')) }
    }
} finally {
    if ($null -ne $hotelOwnedProcess) {
        $hotelOwnedProcess.Refresh()
        if (-not $hotelOwnedProcess.HasExited -and $hotelOwnedProcess.Id -ne 24236) { $hotelOwnedProcess.Kill() }
        $hotelOwnedProcess.Dispose()
    }
    foreach ($hotelEnvName in $hotelEnvNames) {
        [Environment]::SetEnvironmentVariable($hotelEnvName, $hotelPreviousEnv[$hotelEnvName], 'Process')
    }
}
