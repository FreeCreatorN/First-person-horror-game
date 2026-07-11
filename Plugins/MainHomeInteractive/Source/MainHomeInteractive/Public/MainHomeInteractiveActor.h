#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MainHomeInteractiveActor.generated.h"

class APlayerController;
class APawn;
class UBoxComponent;
class UPrimitiveComponent;
class USceneComponent;
class UStaticMesh;
class UStaticMeshComponent;
struct FInputKeyBinding;

UENUM(BlueprintType)
enum class EMainHomeDoorOpenDirection : uint8
{
    Inward,
    Outward
};

namespace MainHomeInteractive
{
    enum class EHitPart : uint8
    {
        None,
        Shutter,
        LeftDoor,
        RightDoor
    };

    struct MAINHOMEINTERACTIVE_API FAnimationState
    {
        float ShutterAlpha = 0.0f;
        float ShutterTarget = 0.0f;
        float LeftDoorAlpha = 0.0f;
        float LeftDoorTarget = 0.0f;
        float RightDoorAlpha = 0.0f;
        float RightDoorTarget = 0.0f;
    };

    MAINHOMEINTERACTIVE_API float ComputeDoorYaw(
        bool bIsLeftDoor,
        EMainHomeDoorOpenDirection Direction,
        float DoorAngleDegrees
    );
    MAINHOMEINTERACTIVE_API float ComputeShutterScale(float Alpha);
    MAINHOMEINTERACTIVE_API float AdvanceAlpha(
        float Current,
        float Target,
        float DeltaSeconds,
        float DurationSeconds
    );
    MAINHOMEINTERACTIVE_API void ToggleShutterTarget(
        FAnimationState& State
    );
    MAINHOMEINTERACTIVE_API void ToggleDoorTarget(
        FAnimationState& State,
        bool bIsLeftDoor
    );
    MAINHOMEINTERACTIVE_API void ConfigureInteractionBinding(
        FInputKeyBinding& Binding
    );
    MAINHOMEINTERACTIVE_API bool ShouldEnableShutterCollision(
        float Alpha,
        float Target
    );
    MAINHOMEINTERACTIVE_API bool IsAnimationMoving(
        const FAnimationState& State
    );
    MAINHOMEINTERACTIVE_API EHitPart ClassifyHitComponent(
        const UPrimitiveComponent* HitComponent,
        const UPrimitiveComponent* ShutterComponent,
        const UPrimitiveComponent* ShutterTraceTargetComponent,
        const UPrimitiveComponent* LeftDoorComponent,
        const UPrimitiveComponent* RightDoorComponent
    );
}

UCLASS(Blueprintable)
class MAINHOMEINTERACTIVE_API AMainHomeInteractiveActor : public AActor
{
    GENERATED_BODY()

public:
    AMainHomeInteractiveActor();

    virtual void Tick(float DeltaSeconds) override;

    UFUNCTION(BlueprintCallable, Category = "Main Home|Interaction")
    void ToggleShutter();

    UFUNCTION(BlueprintCallable, Category = "Main Home|Interaction")
    void ToggleLeftDoor();

    UFUNCTION(BlueprintCallable, Category = "Main Home|Interaction")
    void ToggleRightDoor();

    UFUNCTION(BlueprintCallable, Category = "Main Home|Meshes")
    void SetMainHomeMeshes(
        UStaticMesh* InFixedShell,
        UStaticMesh* InShutter,
        UStaticMesh* InLeftDoor,
        UStaticMesh* InRightDoor
    );

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Main Home|Components", meta = (AllowPrivateAccess = "true"))
    TObjectPtr<USceneComponent> SceneRoot;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Main Home|Components", meta = (AllowPrivateAccess = "true"))
    TObjectPtr<UStaticMeshComponent> FixedShell;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Main Home|Components", meta = (AllowPrivateAccess = "true"))
    TObjectPtr<UStaticMeshComponent> Shutter;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Main Home|Components", meta = (AllowPrivateAccess = "true"))
    TObjectPtr<UBoxComponent> ShutterTraceTarget;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Main Home|Components", meta = (AllowPrivateAccess = "true"))
    TObjectPtr<USceneComponent> LeftHinge;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Main Home|Components", meta = (AllowPrivateAccess = "true"))
    TObjectPtr<UStaticMeshComponent> LeftDoorLeaf;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Main Home|Components", meta = (AllowPrivateAccess = "true"))
    TObjectPtr<USceneComponent> RightHinge;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Main Home|Components", meta = (AllowPrivateAccess = "true"))
    TObjectPtr<UStaticMeshComponent> RightDoorLeaf;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Main Home|Components", meta = (AllowPrivateAccess = "true"))
    TObjectPtr<UBoxComponent> ShutterInteractionZone;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Main Home|Components", meta = (AllowPrivateAccess = "true"))
    TObjectPtr<UBoxComponent> DoorInteractionZone;

    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Main Home|Interaction", meta = (AllowPrivateAccess = "true"))
    EMainHomeDoorOpenDirection DoorOpenDirection;

    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Main Home|Interaction", meta = (AllowPrivateAccess = "true", ClampMin = "0.0", UIMin = "0.0", UIMax = "170.0", Units = "Degrees"))
    float DoorAngleDegrees;

    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Main Home|Interaction", meta = (AllowPrivateAccess = "true", ClampMin = "0.01", Units = "Seconds"))
    float AnimationDurationSeconds;

    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Main Home|Interaction", meta = (AllowPrivateAccess = "true", ClampMin = "1.0", Units = "Centimeters"))
    float InteractionDistanceCm;

    MainHomeInteractive::FAnimationState AnimationState;
    TMap<TWeakObjectPtr<APawn>, int32> LocalPawnOverlapCounts;
    TWeakObjectPtr<APawn> InputPawn;
    TWeakObjectPtr<APlayerController> InputController;
    bool bInteractionKeyBound = false;

    UFUNCTION()
    void HandleInteractionZoneBeginOverlap(
        UPrimitiveComponent* OverlappedComponent,
        AActor* OtherActor,
        UPrimitiveComponent* OtherComponent,
        int32 OtherBodyIndex,
        bool bFromSweep,
        const FHitResult& SweepResult
    );

    UFUNCTION()
    void HandleInteractionZoneEndOverlap(
        UPrimitiveComponent* OverlappedComponent,
        AActor* OtherActor,
        UPrimitiveComponent* OtherComponent,
        int32 OtherBodyIndex
    );

    UFUNCTION()
    void HandleInputPawnDestroyed(AActor* DestroyedActor);

    void HandleInteractPressed();
    void ActivateInputForPawn(APawn* Pawn);
    void DeactivateCurrentInput();
    void RemoveInteractionBinding();
    void ApplyAnimationState();
    void SetTickForAnimationState();
};
