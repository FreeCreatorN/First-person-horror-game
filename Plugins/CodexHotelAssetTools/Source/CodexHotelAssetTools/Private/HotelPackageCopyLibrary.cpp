#include "HotelPackageCopyLibrary.h"
#include "AssetHeaderPatcher.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "GenericPlatform/GenericPlatformFile.h"
#include "EditorFramework/AssetImportData.h"

bool UHotelPackageCopyLibrary::RestorePrivateImportFilename(UAssetImportData* ImportData,UAssetImportData* ReadOnlySourceImportData)
{
    if (!IsValid(ImportData) || !ImportData->GetOutermost()->GetName().StartsWith(TEXT("/Game/CodexGenerated/Hotel/"))) return false;
    if (!IsValid(ReadOnlySourceImportData) || !ReadOnlySourceImportData->GetOutermost()->GetName().StartsWith(TEXT("/Game/CodexGenerated/OldTown/")) || ReadOnlySourceImportData->GetSourceFileCount()!=1) return false;
    FString Filename=FPaths::ConvertRelativePathToFull(ReadOnlySourceImportData->GetFirstFilename());
    FPaths::NormalizeFilename(Filename);
    if (!FPaths::CollapseRelativeDirectories(Filename) || ImportData->GetSourceFileCount()!=1) return false;
    const FAssetImportInfo Before=ImportData->GetSourceData();
    // Store the absolute source identity directly: SanitizeImportFilename's
    // package-relative fallback can resolve a missing legacy source differently.
    ImportData->SourceData.SourceFiles[0].RelativeFilename=Filename;
    const FAssetImportInfo& After=ImportData->GetSourceData();
    return After.SourceFiles.Num()==1 && Before.SourceFiles[0].Timestamp==After.SourceFiles[0].Timestamp
        && Before.SourceFiles[0].FileHash==After.SourceFiles[0].FileHash
        && Before.SourceFiles[0].DisplayLabelName==After.SourceFiles[0].DisplayLabelName
        && FPaths::IsSamePath(ImportData->GetFirstFilename(),Filename);
}

namespace
{
    const FString OriginalMap(TEXT("/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet"));
    const FString HotelRoot(TEXT("/Game/CodexGenerated/Hotel/"));
    FString Absolute(const FString& Path)
    {
        FString Result=FPaths::ConvertRelativePathToFull(Path);
        FPaths::NormalizeFilename(Result);
        if (!FPaths::CollapseRelativeDirectories(Result)) return FString();
        return Result;
    }
    bool IsStrictChild(const FString& Path,const FString& Directory)
    {
        FString Boundary=Absolute(Directory);
        Boundary.RemoveFromEnd(TEXT("/"));
        return Absolute(Path).StartsWith(Boundary+TEXT("/"),ESearchCase::IgnoreCase);
    }
    bool HasSidecar(const FString& File)
    {
        for (const TCHAR* Extension:{TEXT("uexp"),TEXT("ubulk"),TEXT("uptnl"),TEXT("m.ubulk"),TEXT("upayload")})
            if (IFileManager::Get().FileExists(*FPaths::ChangeExtension(File,Extension))) return true;
        return false;
    }
    bool HasPlainProjectAncestors(const FString& Path)
    {
        FString Project=Absolute(FPaths::ProjectDir());
        Project.RemoveFromEnd(TEXT("/"));
        FString Current=Absolute(Path);
        if (!IsStrictChild(Current,Project)) return false;
        IPlatformFile& Physical=IPlatformFile::GetPlatformPhysical();
        for (;;)
        {
            // On Windows this tests every reparse point, including junctions.
            // Reject an unsupported check rather than accepting an unresolved path.
            if (Physical.IsSymlink(*Current)!=ESymlinkResult::NonSymlink) return false;
            if (Current.Equals(Project,ESearchCase::IgnoreCase)) return true;
            const FString Parent=FPaths::GetPath(Current);
            if (Parent.IsEmpty() || Parent==Current) return false;
            Current=Parent;
        }
    }
    FString Json(const TSharedRef<FJsonObject>& Object)
    {
        FString Text;
        const TSharedRef<TJsonWriter<>> Writer=TJsonWriterFactory<>::Create(&Text);
        FJsonSerializer::Serialize(Object,Writer);
        return Text;
    }
    FString RunExactPatch(const FAssetHeaderPatcher::FContext& Context,
        const TMap<FString,FString>& PackageRemapping,const TMap<FString,FString>& ExpectedFiles,
        const TSharedRef<FJsonObject>& Report)
    {
        auto Fail=[&Report](const FString& Error){ Report->SetStringField(TEXT("error"),Error);return Json(Report); };
        if (Context.GetLongPackagePathRemapping().Num()!=PackageRemapping.Num()) return Fail(TEXT("Unexpected package mapping expansion or omission"));
        for (const auto& Pair:Context.GetLongPackagePathRemapping())
            if (PackageRemapping.FindRef(Pair.Key)!=Pair.Value) return Fail(TEXT("Unexpected remapping change"));
        // The patcher truncates existing destinations. Keep every operation a
        // create-only operation, including the final Saved commit candidate.
        for (const auto& Pair:ExpectedFiles)
        {
            if (!IsStrictChild(Pair.Key,Absolute(FPaths::ProjectContentDir())) ||
                !HasPlainProjectAncestors(Pair.Key) || !HasPlainProjectAncestors(Pair.Value))
                return Fail(TEXT("Source or destination resolves through an unsupported path outside the plain project tree"));
            if (IFileManager::Get().FileExists(*Pair.Value) || IFileManager::Get().DirectoryExists(*Pair.Value))
                return Fail(TEXT("Destination appeared before patching: ")+Pair.Value);
            const FString Parent=FPaths::GetPath(Pair.Value);
            if (!IFileManager::Get().MakeDirectory(*Parent,true)) return Fail(TEXT("Cannot create destination directory: ")+Parent);
        }
        FAssetHeaderPatcher Patcher(Context);
        Patcher.PatchAsync().Wait();
        const auto Patched=Patcher.GetPatchedFiles();
        const auto Errors=Patcher.GetErrorFiles();
        TSharedRef<FJsonObject> PatchedJson=MakeShared<FJsonObject>();
        bool bExact=Patched.Num()==ExpectedFiles.Num();
        for (const auto& Pair:Patched)
        {
            const FString Source=Absolute(Pair.Key),Destination=Absolute(Pair.Value);
            PatchedJson->SetStringField(Source,Destination);
            bExact=bExact && ExpectedFiles.FindRef(Source)==Destination && IFileManager::Get().FileExists(*Destination);
        }
        TSharedRef<FJsonObject> ErrorJson=MakeShared<FJsonObject>();
        for (const auto& Pair:Errors) ErrorJson->SetStringField(Pair.Key,LexToString(Pair.Value));
        Report->SetObjectField(TEXT("patched_files"),PatchedJson);
        Report->SetObjectField(TEXT("error_files"),ErrorJson);
        Report->SetStringField(TEXT("patch_result"),LexToString(Patcher.GetPatchResult()));
        Report->SetNumberField(TEXT("expected_written_files"),ExpectedFiles.Num());
        Report->SetBoolField(TEXT("exact_write_set"),bExact);
        Report->SetBoolField(TEXT("passed"),bExact && !Patcher.HasErrors() && Patcher.GetPatchResult()==FAssetHeaderPatcher::EResult::Success);
        return Json(Report);
    }
}

FString UHotelPackageCopyLibrary::PatchPackagesExact(const TMap<FString,FString>& PackageRemapping,
    const TArray<FString>& SourcePackagesToWrite)
{
    TSharedRef<FJsonObject> Report=MakeShared<FJsonObject>();
    Report->SetBoolField(TEXT("passed"),false);
    Report->SetBoolField(TEXT("dependency_gathering"),false);
    Report->SetBoolField(TEXT("source_uobject_load_or_save"),false);
    Report->SetBoolField(TEXT("content_overwrite_permitted"),false);
    auto Fail=[&Report](const FString& Error){ Report->SetStringField(TEXT("error"),Error);return Json(Report); };
    if (PackageRemapping.IsEmpty() || SourcePackagesToWrite.IsEmpty()) return Fail(TEXT("Empty explicit mapping/subset"));
    for (const auto& Pair:PackageRemapping)
    {
        const bool SourceAllowed=Pair.Key==OriginalMap || Pair.Key.StartsWith(TEXT("/Game/CodexGenerated/OldTown/")) || Pair.Key.StartsWith(HotelRoot);
        const bool DestinationAllowed=Pair.Value.StartsWith(HotelRoot);
        if (!SourceAllowed || !DestinationAllowed || !FPackageName::IsValidLongPackageName(Pair.Key) ||
            !FPackageName::IsValidLongPackageName(Pair.Value) || Pair.Key==Pair.Value)
            return Fail(TEXT("Package outside exact allowed Hotel operation: ")+Pair.Key+TEXT(" -> ")+Pair.Value);
    }
    TMap<FString,FString> ExpectedFiles;
    TSet<FString> SourceSet,DestinationSet;
    for (const FString& Source:SourcePackagesToWrite)
    {
        const FString* Destination=PackageRemapping.Find(Source);
        if (!Destination || SourceSet.Contains(Source) || DestinationSet.Contains(*Destination)) return Fail(TEXT("Missing/duplicate explicit source or destination"));
        SourceSet.Add(Source);DestinationSet.Add(*Destination);
        FString SourceFile;
        if (!FPackageName::DoesPackageExist(Source,&SourceFile)) return Fail(TEXT("Missing source package: ")+Source);
        SourceFile=Absolute(SourceFile);
        const FString Extension=FPaths::GetExtension(SourceFile,true);
        if (Extension!=TEXT(".umap") && Extension!=TEXT(".uasset")) return Fail(TEXT("Unexpected source extension"));
        const FString DestinationFile=Absolute(FPackageName::LongPackageNameToFilename(*Destination,Extension));
        if (IFileManager::Get().FileExists(*DestinationFile) || IFileManager::Get().DirectoryExists(*DestinationFile))
            return Fail(TEXT("Destination already exists: ")+DestinationFile);
        if (HasSidecar(SourceFile)) return Fail(TEXT("Separate source bulk sidecar is outside this exact operation"));
        ExpectedFiles.Add(SourceFile,DestinationFile);
    }
    FAssetHeaderPatcher::FContext Context(PackageRemapping,false,&SourcePackagesToWrite);
    return RunExactPatch(Context,PackageRemapping,ExpectedFiles,Report);
}

FString UHotelPackageCopyLibrary::PatchPackagesToSaved(const TMap<FString,FString>& PackageRemapping,
    const TArray<FString>& SourcePackagesToWrite,const FString& SavedOutputBaseDirectory)
{
    TSharedRef<FJsonObject> Report=MakeShared<FJsonObject>();
    Report->SetBoolField(TEXT("passed"),false);
    Report->SetBoolField(TEXT("dependency_gathering"),false);
    Report->SetBoolField(TEXT("source_uobject_load_or_save"),false);
    Report->SetBoolField(TEXT("content_overwrite_permitted"),false);
    Report->SetBoolField(TEXT("writes_only_saved"),true);
    auto Fail=[&Report](const FString& Error){ Report->SetStringField(TEXT("error"),Error);return Json(Report); };
    if (PackageRemapping.IsEmpty() || SourcePackagesToWrite.IsEmpty()) return Fail(TEXT("Empty explicit mapping/subset"));
    const FString ProjectDirectory=Absolute(FPaths::ProjectDir());
    const FString AllowedOutput=Absolute(FPaths::ProjectSavedDir()/TEXT("CodexOutputs/OldTownHotelNaming_20261017"));
    const FString OutputBase=Absolute(SavedOutputBaseDirectory);
    if (!IsStrictChild(OutputBase,AllowedOutput)) return Fail(TEXT("Output base must be a child of this stage's Saved directory"));
    Report->SetStringField(TEXT("saved_output_base_directory"),OutputBase);

    TMap<FString,FString> AllFiles,ExpectedFiles;
    TSet<FString> SourceNames,DestinationNames;
    for (const auto& Pair:PackageRemapping)
    {
        if (!Pair.Key.StartsWith(HotelRoot) ||
            !(Pair.Value.StartsWith(HotelRoot) || Pair.Value==OriginalMap) ||
            !FPackageName::IsValidLongPackageName(Pair.Key) || !FPackageName::IsValidLongPackageName(Pair.Value))
            return Fail(TEXT("Saved patch package outside the private Hotel source/destination scope: ")+Pair.Key+TEXT(" -> ")+Pair.Value);
        const FString SourceKey=Pair.Key.ToLower(),DestinationKey=Pair.Value.ToLower();
        if (SourceNames.Contains(SourceKey) || DestinationNames.Contains(DestinationKey))
            return Fail(TEXT("Case-insensitive duplicate logical source or destination"));
        SourceNames.Add(SourceKey);DestinationNames.Add(DestinationKey);
        FString SourceFile;
        if (!FPackageName::DoesPackageExist(Pair.Key,&SourceFile)) return Fail(TEXT("Missing private Hotel source: ")+Pair.Key);
        SourceFile=Absolute(SourceFile);
        if (!IsStrictChild(SourceFile,ProjectDirectory/TEXT("Content/CodexGenerated/Hotel")))
            return Fail(TEXT("Private source resolved outside the project Hotel directory: ")+SourceFile);
        const FString Extension=FPaths::GetExtension(SourceFile,true);
        if (Extension!=TEXT(".umap") && Extension!=TEXT(".uasset")) return Fail(TEXT("Unexpected source extension"));
        if (Pair.Value==OriginalMap && (Extension!=TEXT(".umap") || !Pair.Key.StartsWith(HotelRoot+TEXT("Maps/"))))
            return Fail(TEXT("Only a private Hotel map may stage the original map's logical name"));
        if (HasSidecar(SourceFile)) return Fail(TEXT("Separate source bulk sidecar is outside this exact operation"));
        const FString DestinationFile=Absolute(OutputBase/TEXT("Content")/(Pair.Value.Mid(6)+Extension));
        if (!IsStrictChild(DestinationFile,OutputBase/TEXT("Content")) ||
            IFileManager::Get().FileExists(*DestinationFile) || IFileManager::Get().DirectoryExists(*DestinationFile))
            return Fail(TEXT("Saved destination escaped the output tree or already exists: ")+DestinationFile);
        AllFiles.Add(SourceFile,DestinationFile);
    }
    TArray<FString> FilesToWrite;
    TSet<FString> WrittenSources;
    for (const FString& Source:SourcePackagesToWrite)
    {
        if (!PackageRemapping.Contains(Source) || WrittenSources.Contains(Source.ToLower()))
            return Fail(TEXT("Missing or duplicate explicit source subset"));
        WrittenSources.Add(Source.ToLower());
        FString SourceFile;
        if (!FPackageName::DoesPackageExist(Source,&SourceFile)) return Fail(TEXT("Missing explicit source package"));
        SourceFile=Absolute(SourceFile);
        const FString* DestinationFile=AllFiles.Find(SourceFile);
        if (!DestinationFile) return Fail(TEXT("Source subset does not match the normalized explicit file mapping"));
        FilesToWrite.Add(SourceFile);ExpectedFiles.Add(SourceFile,*DestinationFile);
    }
    const TMap<FString,FString> EmptyMountReplacements;
    FAssetHeaderPatcher::FContext Context(TEXT("Game"),TEXT("Game"),ProjectDirectory,OutputBase,
        AllFiles,EmptyMountReplacements,&FilesToWrite);
    return RunExactPatch(Context,PackageRemapping,ExpectedFiles,Report);
}
