param(
    [Parameter(Mandatory=$true)][string]$GateCompletionFile
)
# Offline only. Every move names one approved file. No recursive move/delete,
# no force deletion, no redirector repair, no saving or editing user assets.
$ErrorActionPreference='Stop'
$stageRoot='D:\UE\Project\HorrorGame'
$stageWork=Join-Path $stageRoot 'Saved\CodexOutputs\OldTownDoorReuse_20261017'
$stageContent=[IO.Path]::GetFullPath((Join-Path $stageRoot 'Content')).TrimEnd('\','/')
$stageConfig=Join-Path $stageRoot 'Config'
$stageSaved=[IO.Path]::GetFullPath((Join-Path $stageRoot 'Saved')).TrimEnd('\','/')
$stageApprovalFile=Join-Path $stageWork 'OfflineCleanupApproved.json'
$stageBackup=$null

function Assert-NoUnreal {
    $engines=@(Get-Process -Name UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue)
    if ($engines.Count -ne 0) { throw 'All Unreal editor/helper processes must exit before offline isolation.' }
}

function Get-Digest([string]$File) {
    return (Get-FileHash -LiteralPath $File -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
}

function Assert-PlainPath([string]$File,[string]$Boundary) {
    $absolute=[IO.Path]::GetFullPath($File)
    $bound=[IO.Path]::GetFullPath($Boundary).TrimEnd('\','/')
    if (-not $absolute.StartsWith(($bound+'\'),[StringComparison]::OrdinalIgnoreCase)) {
        throw ('Path escaped expected boundary: '+$absolute)
    }
    $current=$absolute
    while ($true) {
        if (Test-Path -LiteralPath $current) {
            $item=Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw ('Junction/symbolic-link path is not permitted: '+$current)
            }
        }
        if ($current.Equals($bound,[StringComparison]::OrdinalIgnoreCase)) { break }
        $parent=[IO.Path]::GetDirectoryName($current)
        if (-not $parent -or $parent -eq $current) { throw 'Boundary was not reached.' }
        $current=$parent
    }
    return $absolute
}

function Assert-HashBag($Bag,[string]$Description) {
    foreach ($entry in $Bag.PSObject.Properties) {
        if ((Get-Digest $entry.Name) -ne $entry.Value) {
            throw ($Description+' hash mismatch: '+$entry.Name)
        }
    }
}

function Write-StageJson([string]$File,$Object) {
    if (Test-Path -LiteralPath $File) { throw ('Evidence already exists: '+$File) }
    ConvertTo-Json -InputObject $Object -Depth 14 |
        Set-Content -LiteralPath $File -Encoding utf8 -ErrorAction Stop
}

Assert-NoUnreal
if (Test-Path -LiteralPath (Join-Path $stageWork 'FinalReview.json')) { throw 'An accepted stage may not be changed.' }
if (Test-Path -LiteralPath (Join-Path $stageWork 'OfflineCleanupResult.json')) { throw 'Offline cleanup was already completed.' }
$approval=Get-Content -LiteralPath $stageApprovalFile -Raw | ConvertFrom-Json
$completionPath=Assert-PlainPath ((Resolve-Path -LiteralPath $GateCompletionFile).ProviderPath) $stageWork
$completion=Get-Content -LiteralPath $completionPath -Raw | ConvertFrom-Json
$completionUtc=if ($completion.completed_utc -is [DateTime]) {
    $completion.completed_utc.ToUniversalTime()
} else {
    [DateTimeOffset]::Parse([string]$completion.completed_utc).UtcDateTime
}
if (-not $approval.passed -or -not $approval.approved_for_offline_quarantine -or
    -not $approval.no_map_save -or -not $approval.no_content_write -or -not $approval.no_delete_api_called) {
    throw 'The read-only UE cleanup gate did not pass.'
}
if (-not $completion.normal_zero_exit -or $completion.exit_code -ne 0 -or
    -not [IO.Path]::GetFullPath($completion.script).Equals((Join-Path $stageRoot 'Scripts\ApproveOldTownUnusedOfflineCleanup.py'),[StringComparison]::OrdinalIgnoreCase) -or
    $completionUtc -lt (Get-Item -LiteralPath $stageApprovalFile).LastWriteTimeUtc) {
    throw 'The exact owned cleanup gate must finish normally before offline moves.'
}
if ($approval.asset_registry_external_references.Count -ne 0) { throw 'An external reference blocks cleanup.' }
$approvalHash=Get-Digest $stageApprovalFile
$completionHash=Get-Digest $completionPath
Assert-HashBag $approval.evidence_sha256 'Gate evidence'
Assert-HashBag $approval.analysis_source_sha256 'Creation/reference analysis evidence'
Assert-HashBag $approval.all_content_config_file_sha256 'Current Content/Config'
Assert-HashBag $approval.protected_file_sha256 'Non-candidate protected file'
$initialActual=@(Get-ChildItem -LiteralPath $stageContent,$stageConfig -Recurse -File | ForEach-Object FullName)
$initialExpected=@($approval.all_content_config_file_sha256.PSObject.Properties.Name)
if (@(Compare-Object -ReferenceObject $initialExpected -DifferenceObject $initialActual).Count -ne 0) {
    throw 'The full Content/Config file set changed after approval.'
}
if ((Get-Digest $approval.map_file) -ne $approval.map_sha256) { throw 'Current original map differs from the approved saved map.' }

$records=@($approval.candidate_files)
if ($records.Count -eq 0 -or $records.Count -ne $approval.candidate_count) { throw 'Approved candidate count mismatch.' }
$seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$protectedPackages=@('/Game/Yastar/Maps/L_Main','/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet',
    '/Game/CodexGenerated/OldTownVersion2/Maps/老城区第二版')
$stamp=(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')+'_'+[guid]::NewGuid().ToString('N').Substring(0,8)
$stageBackup=Join-Path $stageSaved ('CodexBackups\OldTownUnusedResourcesOffline_'+$stamp)
if (Test-Path -LiteralPath $stageBackup) { throw 'A backup isolation directory must be new.' }
$moves=@()
foreach ($record in $records) {
    $source=Assert-PlainPath $record.file $stageContent
    if (-not $seen.Add($source)) { throw 'Duplicate approved source file.' }
    $resolved=(Resolve-Path -LiteralPath $source).ProviderPath
    if (-not $resolved.Equals($source,[StringComparison]::OrdinalIgnoreCase)) { throw 'Resolved source identity changed.' }
    $extension=[IO.Path]::GetExtension($source).ToLowerInvariant()
    if ($extension -notin @('.uasset','.umap')) { throw 'Only exact approved package files may move.' }
    $relative=$source.Substring($stageContent.Length).TrimStart('\','/')
    $package='/Game/'+$relative.Substring(0,$relative.Length-$extension.Length).Replace('\','/')
    if (-not $package.Equals($record.package,[StringComparison]::OrdinalIgnoreCase) -or
        $protectedPackages -contains $package -or
        (-not $package.StartsWith('/Game/CodexGenerated/OldTown/',[StringComparison]::OrdinalIgnoreCase) -and
         $package -ne '/Game/Yastar/Maps/Scenes/L_OldTownHotelReview_20261004')) {
        throw ('Package is outside the exact assistant-owned cleanup scope: '+$package)
    }
    if ($approval.protected_file_sha256.PSObject.Properties[$source]) { throw 'Candidate also appears in the protected set.' }
    if (-not $record.source_origin -or (Get-Digest $source) -ne $record.current_sha256 -or
        $approval.all_content_config_file_sha256.PSObject.Properties[$source].Value -ne $record.current_sha256) {
        throw ('Candidate ownership/hash identity changed: '+$source)
    }
    foreach ($sidecar in @('.uexp','.ubulk','.uptnl')) {
        if (Test-Path -LiteralPath ([IO.Path]::ChangeExtension($source,$sidecar))) { throw 'Unapproved package sidecar exists.' }
    }
    $target=Assert-PlainPath (Join-Path $stageBackup ('Content\'+$relative)) $stageSaved
    $moves += [pscustomobject]@{package=$package;original_path=$source;isolated_path=$target;
        sha256=$record.current_sha256;bytes=(Get-Item -LiteralPath $source).Length}
}
$partition=@($approval.protected_file_sha256.PSObject.Properties.Name)+@($moves.original_path)
if (@(Compare-Object -ReferenceObject $initialExpected -DifferenceObject $partition).Count -ne 0) {
    throw 'Protected files plus exact candidates do not partition the entire approved baseline.'
}
Assert-NoUnreal
[void](New-Item -ItemType Directory -Path $stageBackup -ErrorAction Stop)
$manifestFile=Join-Path $stageBackup 'Manifest.json'
$journalFile=Join-Path $stageBackup 'MoveJournal.jsonl'
Write-StageJson $manifestFile ([ordered]@{passed_preflight=$true;created_utc=(Get-Date).ToUniversalTime().ToString('o');
    approval_file=$stageApprovalFile;approval_sha256=$approvalHash;gate_completion_file=$completionPath;
    gate_completion_sha256=$completionHash;map_sha256=$approval.map_sha256;
    files=$moves;restore='With UE closed, verify each isolated SHA256 and restore only to its exact original_path if absent. No recursive operations or overwrites.'})
try {
    foreach ($move in $moves) {
        Assert-NoUnreal
        if ((Get-Digest $move.original_path) -ne $move.sha256) { throw 'Candidate changed immediately before move.' }
        $null=Assert-PlainPath $move.original_path $stageContent
        $null=Assert-PlainPath $move.isolated_path $stageSaved
        $parent=[IO.Path]::GetDirectoryName($move.isolated_path)
        [void](New-Item -ItemType Directory -Path $parent -Force)
        if (Test-Path -LiteralPath $move.isolated_path) { throw 'An isolated destination may not be overwritten.' }
        ([ordered]@{state='MOVING';source=$move.original_path;destination=$move.isolated_path;sha256=$move.sha256} |
            ConvertTo-Json -Compress) | Add-Content -LiteralPath $journalFile -Encoding utf8
        Move-Item -LiteralPath $move.original_path -Destination $move.isolated_path -ErrorAction Stop
        if ((Test-Path -LiteralPath $move.original_path) -or (Get-Digest $move.isolated_path) -ne $move.sha256) {
            throw 'Isolated file verification failed; consult the exact manifest and journal.'
        }
        ([ordered]@{state='VERIFIED';source=$move.original_path;destination=$move.isolated_path;sha256=$move.sha256} |
            ConvertTo-Json -Compress) | Add-Content -LiteralPath $journalFile -Encoding utf8
    }
    Assert-NoUnreal
    Assert-HashBag $approval.protected_file_sha256 'Protected file after isolation'
    if ((Get-Digest $stageApprovalFile) -ne $approvalHash) { throw 'Approval changed during isolation.' }
    if ((Get-Digest $completionPath) -ne $completionHash) { throw 'Owned helper completion changed during isolation.' }
    $actual=@(Get-ChildItem -LiteralPath $stageContent,$stageConfig -Recurse -File | ForEach-Object FullName)
    $expected=@($approval.protected_file_sha256.PSObject.Properties.Name)
    if (@(Compare-Object -ReferenceObject $expected -DifferenceObject $actual).Count -ne 0) {
        throw 'Unexpected Content/Config file set after isolation.'
    }
    Write-StageJson (Join-Path $stageWork 'OfflineCleanupResult.json') ([ordered]@{passed=$true;
        completed_utc=(Get-Date).ToUniversalTime().ToString('o');isolated_count=$moves.Count;
        map_sha256=$approval.map_sha256;protected_files_unchanged=$true;no_unreal_running=$true;
        exact_file_moves_only=$true;no_force_delete=$true;no_directory_delete=$true;
        isolation_directory=$stageBackup;manifest_file=$manifestFile;manifest_sha256=(Get-Digest $manifestFile);
        journal_file=$journalFile;journal_sha256=(Get-Digest $journalFile);approval_sha256=$approvalHash})
    Write-Output ('OLD_TOWN_OFFLINE_ISOLATION_PASS count='+$moves.Count)
} catch {
    $failure=Join-Path $stageWork 'OfflineCleanupFailure.json'
    if (-not (Test-Path -LiteralPath $failure)) {
        Write-StageJson $failure ([ordered]@{passed=$false;isolation_directory=$stageBackup;
            manifest_file=$manifestFile;journal_file=$journalFile;error=$_.Exception.Message;
            no_automatic_recursive_cleanup=$true})
    }
    throw
}
