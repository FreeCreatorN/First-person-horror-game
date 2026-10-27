#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "OldTownLightCircuitEditorLibrary.generated.h"

class AOldTownLightCircuitActor;
class UBlueprint;

UCLASS()
class CODEXOLDTOWNLIGHTSEDITOR_API UOldTownLightCircuitEditorLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    /** Creates, compiles, and saves only the fixed assistant-owned package. */
    UFUNCTION(BlueprintCallable, Category = "Old Town|Editor")
    static UBlueprint* CreateCircuitBlueprint(const FString& AssetPath);

    /** JSON inspection; does not initialize or modify the circuit. */
    UFUNCTION(BlueprintCallable, Category = "Old Town|Editor")
    static FString InspectCircuit(AOldTownLightCircuitActor* Circuit);

    /** Restores transient previews before explicit asset or world saves. */
    UFUNCTION(BlueprintCallable, Category = "Old Town|Editor")
    static void RestoreAllEditorPreviews();
};
