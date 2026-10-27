#include "OldTownLightCircuitActor.h"

#include "Components/LightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/PointLight.h"
#include "Engine/RectLight.h"
#include "Engine/SpotLight.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"

AOldTownLightCircuitActor::AOldTownLightCircuitActor()
{
    PrimaryActorTick.bCanEverTick = false;
    PrimaryActorTick.bStartWithTickEnabled = false;
    USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("CircuitRoot"));
    Root->SetMobility(EComponentMobility::Static);
    SetRootComponent(Root);
}

ULightComponent* AOldTownLightCircuitActor::GetAllowedLocalLightComponent(AActor* Actor)
{
    if (!IsValid(Actor) ||
        !(Actor->IsA<ARectLight>() || Actor->IsA<ASpotLight>() || Actor->IsA<APointLight>()))
    {
        return nullptr;
    }
    return Actor->FindComponentByClass<ULightComponent>();
}

FString AOldTownLightCircuitActor::GetCircuitConfigurationError() const
{
    if (!IsValid(TargetLampMesh) || TargetLampMesh->GetWorld() != GetWorld())
    {
        return TEXT("A lamp mesh in the same world is required.");
    }
    UStaticMeshComponent* Mesh = TargetLampMesh->GetStaticMeshComponent();
    if (!Mesh || EmissiveMaterialSlot < 0 || EmissiveMaterialSlot >= Mesh->GetNumMaterials() ||
        !Mesh->GetMaterial(EmissiveMaterialSlot))
    {
        return TEXT("The emissive material slot is missing.");
    }
    if (ControlledLights.IsEmpty() || ControlledLights.Num() != BaseIntensities.Num())
    {
        return TEXT("Each controlled local light requires one saved base intensity.");
    }
    TSet<const AActor*> UniqueLights;
    for (int32 Index = 0; Index < ControlledLights.Num(); ++Index)
    {
        AActor* Light = ControlledLights[Index];
        if (!GetAllowedLocalLightComponent(Light) || Light->GetWorld() != GetWorld() ||
            UniqueLights.Contains(Light) || !FMath::IsFinite(BaseIntensities[Index]) ||
            BaseIntensities[Index] <= 0.0f)
        {
            return TEXT("Only unique Rect/Spot/Point lights with positive base intensity in the same world are allowed.");
        }
        UniqueLights.Add(Light);
    }
    return FString();
}

bool AOldTownLightCircuitActor::IsGameCircuit() const
{
    return GetWorld() && GetWorld()->IsGameWorld();
}

void AOldTownLightCircuitActor::BeginPlay()
{
    Super::BeginPlay();
    const FString Error = GetCircuitConfigurationError();
    if (!Error.IsEmpty())
    {
        UE_LOG(LogTemp, Error, TEXT("OldTown circuit %s: %s"), *GetPathName(), *Error);
        return;
    }
    if (!EnsureDynamicMaterial())
    {
        return;
    }
    bRuntimeInitialized = true;
    // Respect successful calls from the level script or a Blueprint BeginPlay event.
    ApplyLevel(bLevelApplied ? CurrentLevel : (bInitiallyOn ? 1.0f : 0.0f));
}

void AOldTownLightCircuitActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    RestoreEditorPreview();
    Super::EndPlay(EndPlayReason);
}

void AOldTownLightCircuitActor::CaptureEditorPreviewState()
{
    if (bPreviewCaptured || IsGameCircuit() || !IsValid(TargetLampMesh))
    {
        return;
    }
    PreviewOriginalMaterial = TargetLampMesh->GetStaticMeshComponent()->GetMaterial(EmissiveMaterialSlot);
    for (AActor* Light : ControlledLights)
    {
        if (ULightComponent* Component = GetAllowedLocalLightComponent(Light))
        {
            PreviewLightComponents.Add(Component);
            PreviewOriginalIntensities.Add(Component->Intensity);
            PreviewOriginalVisibility.Add(Component->IsVisible());
            PreviewOriginalHiddenInGame.Add(Component->bHiddenInGame);
        }
    }
    bPreviewCaptured = true;
}

bool AOldTownLightCircuitActor::EnsureDynamicMaterial()
{
    if (IsValid(LampMID))
    {
        return true;
    }
    const FString Error = GetCircuitConfigurationError();
    if (!Error.IsEmpty())
    {
        UE_LOG(LogTemp, Warning, TEXT("OldTown circuit %s: %s"), *GetPathName(), *Error);
        return false;
    }
    CaptureEditorPreviewState();
    UStaticMeshComponent* Mesh = TargetLampMesh->GetStaticMeshComponent();
    LampMID = UMaterialInstanceDynamic::Create(Mesh->GetMaterial(EmissiveMaterialSlot), this);
    if (!LampMID)
    {
        return false;
    }
    LampMID->SetFlags(RF_Transient | RF_DuplicateTransient);
    Mesh->SetMaterial(EmissiveMaterialSlot, LampMID);
    return true;
}

void AOldTownLightCircuitActor::ApplyLevel(const float Level)
{
    bLevelApplied = true;
    CurrentLevel = FMath::Clamp(FMath::IsFinite(Level) ? Level : 0.0f, 0.0f, 1.0f);
    const bool bOn = CurrentLevel > 0.0f;
    if (LampMID)
    {
        LampMID->SetScalarParameterValue(TEXT("LightStrength"), 20.0f * CurrentLevel);
    }
    for (int32 Index = 0; Index < ControlledLights.Num(); ++Index)
    {
        if (ULightComponent* Component = GetAllowedLocalLightComponent(ControlledLights[Index]))
        {
            Component->SetIntensity(BaseIntensities.IsValidIndex(Index) ? BaseIntensities[Index] * CurrentLevel : 0.0f);
            Component->SetVisibility(bOn, false);
            Component->SetHiddenInGame(!bOn, false);
        }
    }
}

void AOldTownLightCircuitActor::SetLightOn(const bool bOn)
{
    SetLightLevel(bOn ? 1.0f : 0.0f);
}

void AOldTownLightCircuitActor::ToggleLight()
{
    SetLightOn(!GetLightState());
}

void AOldTownLightCircuitActor::SetLightLevel(const float Level)
{
    if (EnsureDynamicMaterial())
    {
        ApplyLevel(Level);
    }
}

bool AOldTownLightCircuitActor::GetLightState() const
{
    return GetLightLevel() > 0.0f;
}

float AOldTownLightCircuitActor::GetLightLevel() const
{
    return bLevelApplied ? CurrentLevel : (bInitiallyOn ? 1.0f : 0.0f);
}

FText AOldTownLightCircuitActor::GetInteractText() const
{
    return FText::FromString(GetLightState() ? TEXT("关灯") : TEXT("开灯"));
}

FText AOldTownLightCircuitActor::GetCircuitInteractText() const
{
    return GetInteractText();
}

void AOldTownLightCircuitActor::SetCircuitHighlight(const bool bEnabled)
{
    if (IsGameCircuit() && IsValid(TargetLampMesh))
    {
        TargetLampMesh->GetStaticMeshComponent()->SetRenderCustomDepth(bEnabled);
    }
}

void AOldTownLightCircuitActor::PreviewOn()
{
    SetLightOn(true);
}

void AOldTownLightCircuitActor::PreviewOff()
{
    SetLightOn(false);
}

void AOldTownLightCircuitActor::RestoreEditorPreview()
{
    if (!bPreviewCaptured)
    {
        return;
    }
    if (IsValid(TargetLampMesh))
    {
        TargetLampMesh->GetStaticMeshComponent()->SetMaterial(EmissiveMaterialSlot, PreviewOriginalMaterial);
    }
    for (int32 Index = 0; Index < PreviewLightComponents.Num(); ++Index)
    {
        if (ULightComponent* Component = PreviewLightComponents[Index])
        {
            Component->SetIntensity(PreviewOriginalIntensities[Index]);
            Component->SetVisibility(PreviewOriginalVisibility[Index], false);
            Component->SetHiddenInGame(PreviewOriginalHiddenInGame[Index], false);
        }
    }
    LampMID = nullptr;
    PreviewOriginalMaterial = nullptr;
    PreviewLightComponents.Reset();
    PreviewOriginalIntensities.Reset();
    PreviewOriginalVisibility.Reset();
    PreviewOriginalHiddenInGame.Reset();
    bPreviewCaptured = false;
    bLevelApplied = false;
    CurrentLevel = bInitiallyOn ? 1.0f : 0.0f;
}
