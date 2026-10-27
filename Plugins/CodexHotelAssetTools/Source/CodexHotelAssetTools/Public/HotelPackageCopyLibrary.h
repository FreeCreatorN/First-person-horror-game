#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "HotelPackageCopyLibrary.generated.h"
class UAssetImportData;

UCLASS()
class CODEXHOTELASSETTOOLS_API UHotelPackageCopyLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Correct a private Hotel copy's moved source path without reimporting or changing timestamp/hash. Does not save. */
    UFUNCTION(BlueprintCallable, Category="Hotel|Editor")
    static bool RestorePrivateImportFilename(UAssetImportData* ImportData, UAssetImportData* ReadOnlySourceImportData);

    /** Exact explicit files only; no dependency gathering, UObject mutation, source saves or redirector creation. */
    UFUNCTION(BlueprintCallable, Category="Hotel|Editor")
    static FString PatchPackagesExact(const TMap<FString,FString>& PackageRemapping,
        const TArray<FString>& SourcePackagesToWrite);

    /** Patch private Hotel packages into a new Saved staging tree, preserving the requested logical package names. Never writes Content. */
    UFUNCTION(BlueprintCallable, Category="Hotel|Editor")
    static FString PatchPackagesToSaved(const TMap<FString,FString>& PackageRemapping,
        const TArray<FString>& SourcePackagesToWrite, const FString& SavedOutputBaseDirectory);
};
