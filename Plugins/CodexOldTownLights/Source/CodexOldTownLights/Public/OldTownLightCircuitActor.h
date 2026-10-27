#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "OldTownLightCircuitActor.generated.h"

class AStaticMeshActor;
class ULightComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;

/** A controller only: it never creates a mesh, light, interaction hotspot, or input binding. */
UCLASS(Blueprintable)
class CODEXOLDTOWNLIGHTS_API AOldTownLightCircuitActor : public AActor
{
    GENERATED_BODY()

public:
    AOldTownLightCircuitActor();

    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Old Town|Circuit")
    TObjectPtr<AStaticMeshActor> TargetLampMesh;

    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Old Town|Circuit", meta = (ClampMin = "0"))
    int32 EmissiveMaterialSlot = 2;

    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Old Town|Circuit")
    TArray<TObjectPtr<AActor>> ControlledLights;

    /** Photometric values captured from the saved local lights. One value per light. */
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Old Town|Circuit")
    TArray<float> BaseIntensities;

    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Old Town|Circuit")
    bool bInitiallyOn = true;

    UFUNCTION(BlueprintCallable, Category = "Old Town|Circuit")
    void SetLightOn(bool bOn);

    UFUNCTION(BlueprintCallable, Category = "Old Town|Circuit", CallInEditor)
    void ToggleLight();

    UFUNCTION(BlueprintCallable, Category = "Old Town|Circuit")
    void SetLightLevel(float Level);

    UFUNCTION(BlueprintPure, Category = "Old Town|Circuit")
    bool GetLightState() const;

    UFUNCTION(BlueprintPure, Category = "Old Town|Circuit")
    float GetLightLevel() const;

    FText GetInteractText() const;

    /** Different native name avoids conflicting with the existing Blueprint interface function. */
    UFUNCTION(BlueprintPure, Category = "Old Town|Circuit", meta = (DisplayName = "Get Interact Text"))
    FText GetCircuitInteractText() const;

    UFUNCTION(BlueprintCallable, Category = "Old Town|Circuit")
    void SetCircuitHighlight(bool bEnabled);

    UFUNCTION(BlueprintCallable, Category = "Old Town|Preview", CallInEditor)
    void PreviewOn();

    UFUNCTION(BlueprintCallable, Category = "Old Town|Preview", CallInEditor)
    void PreviewOff();

    /** Also called globally before any editor world save or PIE duplication. */
    UFUNCTION(BlueprintCallable, Category = "Old Town|Preview", CallInEditor)
    void RestoreEditorPreview();

    UFUNCTION(BlueprintPure, Category = "Old Town|Diagnostics")
    bool HasInitializedLightCircuit() const { return bRuntimeInitialized; }

    UFUNCTION(BlueprintPure, Category = "Old Town|Diagnostics")
    UMaterialInstanceDynamic* GetLampDynamicMaterial() const { return LampMID; }

    UFUNCTION(BlueprintPure, Category = "Old Town|Diagnostics")
    FString GetCircuitConfigurationError() const;

    static ULightComponent* GetAllowedLocalLightComponent(AActor* Actor);

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    UPROPERTY(Transient)
    TObjectPtr<UMaterialInstanceDynamic> LampMID;

    UPROPERTY(Transient)
    TObjectPtr<UMaterialInterface> PreviewOriginalMaterial;

    UPROPERTY(Transient)
    TArray<TObjectPtr<ULightComponent>> PreviewLightComponents;

    UPROPERTY(Transient)
    TArray<float> PreviewOriginalIntensities;

    UPROPERTY(Transient)
    TArray<bool> PreviewOriginalVisibility;

    UPROPERTY(Transient)
    TArray<bool> PreviewOriginalHiddenInGame;

    UPROPERTY(Transient)
    bool bPreviewCaptured = false;

    UPROPERTY(Transient)
    bool bRuntimeInitialized = false;

    UPROPERTY(Transient)
    bool bLevelApplied = false;

    UPROPERTY(Transient)
    float CurrentLevel = 0.0f;

    bool IsGameCircuit() const;
    void CaptureEditorPreviewState();
    bool EnsureDynamicMaterial();
    void ApplyLevel(float Level);
};
