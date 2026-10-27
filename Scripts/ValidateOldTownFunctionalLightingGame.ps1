param([ValidatePattern('^[A-Za-z0-9_-]+$')][string]$RunName='RuntimeGame1')
$ErrorActionPreference='Stop'
$lightingRoot='D:\UE\Project\HorrorGame'
$lightingWork=Join-Path $lightingRoot 'Saved\CodexOutputs\OldTownFunctionalLighting_20261017'
$lightingAppliedPath=Join-Path $lightingWork 'Applied.json'
$lightingApplied=Get-Content -LiteralPath $lightingAppliedPath -Raw | ConvertFrom-Json
$lightingSourceSha1=(Get-FileHash -LiteralPath $lightingAppliedPath -Algorithm SHA1).Hash.ToLowerInvariant()
$lightingMap=Join-Path $lightingRoot 'Content\Yastar\Maps\Scenes\L_OldTownSchoolStreet.umap'
if ((Get-FileHash -LiteralPath $lightingMap).Hash.ToLowerInvariant() -ne $lightingApplied.map_sha256) { throw 'Map changed before game verification.' }
if (@(Get-Process -Name UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count -ne 0) { throw 'Another helper is running.' }
$lightingOldCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
try {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',(Join-Path $lightingRoot 'Saved\CodexDDC'),'Process')
    $lightingStart=Get-Date
    $lightingProcess=Start-Process -FilePath 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' -ArgumentList @(
        ('"'+(Join-Path $lightingRoot 'HorrorGame.uproject')+'"'),
        '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet','-game','-NullRHI','-RenderOffscreen','-unattended','-nop4','-NoSound','-NoSplash','-NoAutoSave','-NOINI','-nocef',
        '-ExecCmds="CodexOldTownLights.Validate"','-CodexLightCircuitCount=33','-CodexLightInitiallyOn=13','-CodexLightValidationDir=Saved/CodexOutputs/OldTownFunctionalLighting_20261017','-DDC=InstalledNoZenLocalFallback',
        '-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=D:/UE/Project/HorrorGame/Saved/CodexDDC,EnvPathOverride=UE-LocalDataCachePath)',
        '-stdout','-FullStdOutLogOutput','-UTF8Output','-FORCELOGFLUSH',('-abslog="'+(Join-Path $lightingWork ($RunName+'.log'))+'"')
    ) -WorkingDirectory $lightingRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $lightingWork ($RunName+'.stdout.log')) -RedirectStandardError (Join-Path $lightingWork ($RunName+'.stderr.log')) -PassThru
    [ordered]@{owned_pid=$lightingProcess.Id;start_utc=$lightingStart.ToUniversalTime().ToString('o');map_sha256=$lightingApplied.map_sha256;map_save_requested=$false;window_style='Hidden'} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $lightingWork ($RunName+'.OwnedProcess.json')) -Encoding utf8
    $lightingForced=$false
    while (-not $lightingProcess.HasExited) {
        if (((Get-Date)-$lightingStart).TotalSeconds -gt 180) {
            $lightingProcess.Kill();$lightingForced=$true;break
        }
        $lightingProcess.WaitForExit(1000) | Out-Null
    }
    $lightingProcess.WaitForExit()
    $lightingExit=$lightingProcess.ExitCode
    $lightingValidationPath=Join-Path $lightingWork 'RuntimeValidation.json'
    $lightingValidation=Get-Content -LiteralPath $lightingValidationPath -Raw | ConvertFrom-Json
    $lightingReportFresh=(Get-Item -LiteralPath $lightingValidationPath).LastWriteTimeUtc -ge $lightingStart.ToUniversalTime()
    $lightingReportOwned=[long]$lightingValidation.owned_process_id -eq [long]$lightingProcess.Id
    $lightingCountsMatch=([int]$lightingValidation.expected_circuit_count -eq 33 -and
        [int]$lightingValidation.expected_initial_on_count -eq 13 -and
        [int]$lightingValidation.expected_initial_off_count -eq 20 -and
        [int]$lightingValidation.circuit_count -eq 33 -and
        [int]$lightingValidation.initial_on_count -eq 13 -and
        [int]$lightingValidation.initial_off_count -eq 20)
    $lightingSourceUnchanged=(Get-FileHash -LiteralPath $lightingAppliedPath -Algorithm SHA1).Hash.ToLowerInvariant() -eq $lightingSourceSha1
    $lightingSourceBound=($lightingSourceUnchanged -and
        $lightingValidation.source_evidence_sha1 -eq $lightingSourceSha1 -and
        $lightingValidation.source_evidence_unchanged -eq $true -and
        $lightingValidation.source_evidence_world_matches -eq $true)
    if ((Get-FileHash -LiteralPath $lightingMap).Hash.ToLowerInvariant() -ne $lightingApplied.map_sha256) { throw 'Map changed during game verification.' }
    $lightingPassed=(-not $lightingForced -and $lightingExit -eq 0 -and $lightingValidation.passed -eq $true -and
        $lightingValidation.game_world -eq $true -and $lightingValidation.world_begun_play -eq $true -and
        $lightingReportFresh -and $lightingReportOwned -and $lightingCountsMatch -and $lightingSourceBound)
    [ordered]@{passed=$lightingPassed;exit_code=$lightingExit;normal_zero_exit=($lightingExit -eq 0 -and -not $lightingForced);forced=$lightingForced;owned_pid=$lightingProcess.Id;map_sha256=$lightingApplied.map_sha256;map_unchanged=$true;
        runtime_report_fresh=$lightingReportFresh;runtime_report_owned_pid_matches=$lightingReportOwned;runtime_expected_and_actual_counts_match=$lightingCountsMatch;
        source_evidence_sha1=$lightingSourceSha1;source_evidence_binding_matches=$lightingSourceBound;completed_utc=(Get-Date).ToUniversalTime().ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $lightingWork ($RunName+'.Completion.json')) -Encoding utf8
    Write-Output ('GAME_VALIDATION_EXIT='+$lightingExit+' PASSED='+$lightingPassed)
    if (-not $lightingPassed) { throw 'Runtime validation failed; inspect report.' }
} finally { [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$lightingOldCache,'Process') }
