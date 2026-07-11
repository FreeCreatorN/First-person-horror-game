#include "MainHomeInteractiveActor.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/BoxComponent.h"
#include "Components/InputComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "UObject/ConstructorHelpers.h"

namespace MainHomeInteractive
{
    float ComputeDoorYaw(
        const bool bIsLeftDoor,
        const EMainHomeDoorOpenDirection Direction,
        const float DoorAngleDegrees
    )
    {
        const float SideSign = bIsLeftDoor ? -1.0f : 1.0f;
        const float DirectionSign =
            Direction == EMainHomeDoorOpenDirection::Outward ? 1.0f : -1.0f;
        return FMath::Abs(DoorAngleDegrees) * SideSign * DirectionSign;
    }

    float ComputeShutterScale(const float Alpha)
    {
        return FMath::Lerp(1.0f, 0.03f, FMath::Clamp(Alpha, 0.0f, 1.0f));
    }

    float AdvanceAlpha(
        const float Current,
        const float Target,
        const float DeltaSeconds,
        const float DurationSeconds
    )
    {
        const float ClampedCurrent = FMath::Clamp(Current, 0.0f, 1.0f);
        const float ClampedTarget = FMath::Clamp(Target, 0.0f, 1.0f);
        if (FMath::IsNearlyEqual(ClampedCurrent, ClampedTarget))
        {
            return ClampedTarget;
        }
        if (DurationSeconds <= UE_SMALL_NUMBER)
        {
            return ClampedTarget;
        }

        const float Step = FMath::Max(0.0f, DeltaSeconds) / DurationSeconds;
        return ClampedCurrent < ClampedTarget
            ? FMath::Min(ClampedCurrent + Step, ClampedTarget)
            : FMath::Max(ClampedCurrent - Step, ClampedTarget);
    }

    void ToggleShutterTarget(FAnimationState& State)
    {
        State.ShutterTarget = State.ShutterTarget >= 0.5f ? 0.0f : 1.0f;
    }

    void ToggleDoorTarget(FAnimationState& State, const bool bIsLeftDoor)
    {
        float& Target = bIsLeftDoor
            ? State.LeftDoorTarget
            : State.RightDoorTarget;
        Target = Target >= 0.5f ? 0.0f : 1.0f;
    }

    void ConfigureInteractionBinding(FInputKeyBinding& Binding)
    {
        Binding.bConsumeInput = false;
    }

    FVector GetShutterTraceTargetLocation()
    {
        return FVector(-96.0f, -394.0f, 263.0f);
    }

    FVector GetShutterTraceTargetExtent()
    {
        return FVector(114.5f, 0.25f, 3.0f);
    }

    bool ShouldEnableShutterCollision(const float Alpha, const float Target)
    {
        return !(
            FMath::IsNearlyEqual(Alpha, 1.0f)
            && FMath::IsNearlyEqual(Target, 1.0f)
        );
    }

    bool IsAnimationMoving(const FAnimationState& State)
    {
        return !FMath::IsNearlyEqual(State.ShutterAlpha, State.ShutterTarget)
            || !FMath::IsNearlyEqual(State.LeftDoorAlpha, State.LeftDoorTarget)
            || !FMath::IsNearlyEqual(State.RightDoorAlpha, State.RightDoorTarget);
    }

    EHitPart ClassifyHitComponent(
        const UPrimitiveComponent* HitComponent,
        const UPrimitiveComponent* ShutterComponent,
        const UPrimitiveComponent* ShutterTraceTargetComponent,
        const UPrimitiveComponent* LeftDoorComponent,
        const UPrimitiveComponent* RightDoorComponent
    )
    {
        if (HitComponent == nullptr)
        {
            return EHitPart::None;
        }
        if (
            HitComponent == ShutterComponent
            || HitComponent == ShutterTraceTargetComponent
        )
        {
            return EHitPart::Shutter;
        }
        if (HitComponent == LeftDoorComponent)
        {
            return EHitPart::LeftDoor;
        }
        if (HitComponent == RightDoorComponent)
        {
            return EHitPart::RightDoor;
        }
        return EHitPart::None;
    }
}

AMainHomeInteractiveActor::AMainHomeInteractiveActor()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = false;

    DoorOpenDirection = EMainHomeDoorOpenDirection::Outward;
    DoorAngleDegrees = 95.0f;
    AnimationDurationSeconds = 0.65f;
    InteractionDistanceCm = 350.0f;

    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
    SceneRoot->SetMobility(EComponentMobility::Static);
    SetRootComponent(SceneRoot);

    FixedShell = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("FixedShell"));
    FixedShell->SetupAttachment(SceneRoot);
    FixedShell->SetMobility(EComponentMobility::Static);
    FixedShell->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);

    Shutter = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Shutter"));
    Shutter->SetupAttachment(SceneRoot);
    Shutter->SetMobility(EComponentMobility::Movable);
    Shutter->SetRelativeLocation(FVector(-96.0f, -394.5f, 277.0f));
    Shutter->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);

    ShutterTraceTarget = CreateDefaultSubobject<UBoxComponent>(TEXT("ShutterTraceTarget"));
    ShutterTraceTarget->SetupAttachment(SceneRoot);
    ShutterTraceTarget->SetMobility(EComponentMobility::Static);
    // Closed shutter bounds are X [-211, 19], Y [-394.5, -391.5], Z [15, 277].
    // Keep a fixed, inset aiming strip just below the hood while leaving the opening clear.
    ShutterTraceTarget->SetRelativeLocation(MainHomeInteractive::GetShutterTraceTargetLocation());
    ShutterTraceTarget->SetBoxExtent(MainHomeInteractive::GetShutterTraceTargetExtent());
    ShutterTraceTarget->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    ShutterTraceTarget->SetCollisionObjectType(ECC_WorldDynamic);
    ShutterTraceTarget->SetCollisionResponseToAllChannels(ECR_Ignore);
    ShutterTraceTarget->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
    ShutterTraceTarget->SetGenerateOverlapEvents(false);
    ShutterTraceTarget->SetVisibility(false);
    ShutterTraceTarget->SetHiddenInGame(true);

    LeftHinge = CreateDefaultSubobject<USceneComponent>(TEXT("LeftHinge"));
    LeftHinge->SetupAttachment(SceneRoot);
    LeftHinge->SetMobility(EComponentMobility::Movable);
    LeftHinge->SetRelativeLocation(FVector(78.0f, -394.0f, 120.0f));

    LeftDoorLeaf = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("LeftDoorLeaf"));
    LeftDoorLeaf->SetupAttachment(LeftHinge);
    LeftDoorLeaf->SetMobility(EComponentMobility::Movable);
    LeftDoorLeaf->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);

    RightHinge = CreateDefaultSubobject<USceneComponent>(TEXT("RightHinge"));
    RightHinge->SetupAttachment(SceneRoot);
    RightHinge->SetMobility(EComponentMobility::Movable);
    RightHinge->SetRelativeLocation(FVector(210.0f, -394.0f, 120.0f));

    RightDoorLeaf = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("RightDoorLeaf"));
    RightDoorLeaf->SetupAttachment(RightHinge);
    RightDoorLeaf->SetMobility(EComponentMobility::Movable);
    RightDoorLeaf->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);

    ShutterInteractionZone = CreateDefaultSubobject<UBoxComponent>(TEXT("ShutterInteractionZone"));
    ShutterInteractionZone->SetupAttachment(SceneRoot);
    ShutterInteractionZone->SetRelativeLocation(FVector(-96.0f, -430.0f, 151.0f));
    ShutterInteractionZone->SetBoxExtent(FVector(145.0f, 90.0f, 150.0f));

    DoorInteractionZone = CreateDefaultSubobject<UBoxComponent>(TEXT("DoorInteractionZone"));
    DoorInteractionZone->SetupAttachment(SceneRoot);
    DoorInteractionZone->SetRelativeLocation(FVector(144.0f, -430.0f, 151.0f));
    DoorInteractionZone->SetBoxExtent(FVector(95.0f, 90.0f, 150.0f));

    for (UBoxComponent* Zone : {ShutterInteractionZone.Get(), DoorInteractionZone.Get()})
    {
        Zone->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
        Zone->SetCollisionObjectType(ECC_WorldDynamic);
        Zone->SetCollisionResponseToAllChannels(ECR_Ignore);
        Zone->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
        Zone->SetGenerateOverlapEvents(true);
        Zone->OnComponentBeginOverlap.AddDynamic(
            this,
            &AMainHomeInteractiveActor::HandleInteractionZoneBeginOverlap
        );
        Zone->OnComponentEndOverlap.AddDynamic(
            this,
            &AMainHomeInteractiveActor::HandleInteractionZoneEndOverlap
        );
    }

    ConstructorHelpers::FObjectFinderOptional<UStaticMesh> ShellMesh(
        TEXT("/Game/MainHome/SM_MainHome_Enterable"),
        LOAD_Quiet | LOAD_NoWarn
    );
    ConstructorHelpers::FObjectFinderOptional<UStaticMesh> ShutterMesh(
        TEXT("/Game/MainHome/SM_MainHome_Shutter"),
        LOAD_Quiet | LOAD_NoWarn
    );
    ConstructorHelpers::FObjectFinderOptional<UStaticMesh> LeftDoorMesh(
        TEXT("/Game/MainHome/SM_MainHome_Door_Left"),
        LOAD_Quiet | LOAD_NoWarn
    );
    ConstructorHelpers::FObjectFinderOptional<UStaticMesh> RightDoorMesh(
        TEXT("/Game/MainHome/SM_MainHome_Door_Right"),
        LOAD_Quiet | LOAD_NoWarn
    );
    SetMainHomeMeshes(
        ShellMesh.Get(),
        ShutterMesh.Get(),
        LeftDoorMesh.Get(),
        RightDoorMesh.Get()
    );
}

void AMainHomeInteractiveActor::BeginPlay()
{
    Super::BeginPlay();
    ApplyAnimationState();
    SetActorTickEnabled(false);
}

void AMainHomeInteractiveActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    DeactivateCurrentInput();
    LocalPawnOverlapCounts.Reset();
    Super::EndPlay(EndPlayReason);
}

void AMainHomeInteractiveActor::Tick(const float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);

    AnimationState.ShutterAlpha = MainHomeInteractive::AdvanceAlpha(
        AnimationState.ShutterAlpha,
        AnimationState.ShutterTarget,
        DeltaSeconds,
        AnimationDurationSeconds
    );
    AnimationState.LeftDoorAlpha = MainHomeInteractive::AdvanceAlpha(
        AnimationState.LeftDoorAlpha,
        AnimationState.LeftDoorTarget,
        DeltaSeconds,
        AnimationDurationSeconds
    );
    AnimationState.RightDoorAlpha = MainHomeInteractive::AdvanceAlpha(
        AnimationState.RightDoorAlpha,
        AnimationState.RightDoorTarget,
        DeltaSeconds,
        AnimationDurationSeconds
    );

    ApplyAnimationState();
    SetTickForAnimationState();
}

void AMainHomeInteractiveActor::ToggleShutter()
{
    MainHomeInteractive::ToggleShutterTarget(AnimationState);
    if (MainHomeInteractive::ShouldEnableShutterCollision(
        AnimationState.ShutterAlpha,
        AnimationState.ShutterTarget
    ))
    {
        Shutter->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    }
    SetTickForAnimationState();
}

void AMainHomeInteractiveActor::ToggleLeftDoor()
{
    MainHomeInteractive::ToggleDoorTarget(AnimationState, true);
    SetTickForAnimationState();
}

void AMainHomeInteractiveActor::ToggleRightDoor()
{
    MainHomeInteractive::ToggleDoorTarget(AnimationState, false);
    SetTickForAnimationState();
}

void AMainHomeInteractiveActor::SetMainHomeMeshes(
    UStaticMesh* InFixedShell,
    UStaticMesh* InShutter,
    UStaticMesh* InLeftDoor,
    UStaticMesh* InRightDoor
)
{
    FixedShell->SetStaticMesh(InFixedShell);
    Shutter->SetStaticMesh(InShutter);
    LeftDoorLeaf->SetStaticMesh(InLeftDoor);
    RightDoorLeaf->SetStaticMesh(InRightDoor);
}

void AMainHomeInteractiveActor::HandleInteractionZoneBeginOverlap(
    UPrimitiveComponent* OverlappedComponent,
    AActor* OtherActor,
    UPrimitiveComponent* OtherComponent,
    int32 OtherBodyIndex,
    bool bFromSweep,
    const FHitResult& SweepResult
)
{
    APawn* Pawn = Cast<APawn>(OtherActor);
    if (Pawn == nullptr || !Pawn->IsLocallyControlled())
    {
        return;
    }

    int32& OverlapCount = LocalPawnOverlapCounts.FindOrAdd(Pawn);
    ++OverlapCount;
    if (!InputPawn.IsValid())
    {
        ActivateInputForPawn(Pawn);
    }
}

void AMainHomeInteractiveActor::HandleInteractionZoneEndOverlap(
    UPrimitiveComponent* OverlappedComponent,
    AActor* OtherActor,
    UPrimitiveComponent* OtherComponent,
    int32 OtherBodyIndex
)
{
    APawn* Pawn = Cast<APawn>(OtherActor);
    if (Pawn == nullptr)
    {
        return;
    }

    int32* OverlapCount = LocalPawnOverlapCounts.Find(Pawn);
    if (OverlapCount == nullptr)
    {
        return;
    }

    --(*OverlapCount);
    if (*OverlapCount > 0)
    {
        return;
    }
    LocalPawnOverlapCounts.Remove(Pawn);

    if (InputPawn.Get() != Pawn)
    {
        return;
    }

    DeactivateCurrentInput();
    for (const TPair<TWeakObjectPtr<APawn>, int32>& Pair : LocalPawnOverlapCounts)
    {
        if (Pair.Value > 0 && Pair.Key.IsValid())
        {
            ActivateInputForPawn(Pair.Key.Get());
            break;
        }
    }
}

void AMainHomeInteractiveActor::HandleInteractPressed()
{
    APlayerController* Controller = InputController.Get();
    APawn* Pawn = InputPawn.Get();
    if (Controller == nullptr || Pawn == nullptr || Controller->PlayerCameraManager == nullptr)
    {
        return;
    }

    const FVector TraceStart = Controller->PlayerCameraManager->GetCameraLocation();
    const FVector TraceEnd = TraceStart
        + Controller->PlayerCameraManager->GetCameraRotation().Vector()
        * FMath::Max(1.0f, InteractionDistanceCm);
    FCollisionQueryParams QueryParams(SCENE_QUERY_STAT(MainHomeInteraction), true);
    QueryParams.AddIgnoredActor(Pawn);

    FHitResult Hit;
    if (!GetWorld()->LineTraceSingleByChannel(
        Hit,
        TraceStart,
        TraceEnd,
        ECC_Visibility,
        QueryParams
    ) || Hit.GetActor() != this)
    {
        return;
    }

    switch (MainHomeInteractive::ClassifyHitComponent(
        Hit.GetComponent(),
        Shutter,
        ShutterTraceTarget,
        LeftDoorLeaf,
        RightDoorLeaf
    ))
    {
    case MainHomeInteractive::EHitPart::Shutter:
        ToggleShutter();
        break;
    case MainHomeInteractive::EHitPart::LeftDoor:
        ToggleLeftDoor();
        break;
    case MainHomeInteractive::EHitPart::RightDoor:
        ToggleRightDoor();
        break;
    default:
        break;
    }
}

void AMainHomeInteractiveActor::ActivateInputForPawn(APawn* Pawn)
{
    APlayerController* Controller = Pawn != nullptr
        ? Cast<APlayerController>(Pawn->GetController())
        : nullptr;
    if (Controller == nullptr || !Controller->IsLocalController())
    {
        return;
    }

    DeactivateCurrentInput();
    EnableInput(Controller);
    InputPawn = Pawn;
    InputController = Controller;
    Pawn->OnDestroyed.AddUniqueDynamic(
        this,
        &AMainHomeInteractiveActor::HandleInputPawnDestroyed
    );

    if (InputComponent != nullptr && !bInteractionKeyBound)
    {
        FInputKeyBinding& InteractionBinding = InputComponent->BindKey(
            EKeys::E,
            IE_Pressed,
            this,
            &AMainHomeInteractiveActor::HandleInteractPressed
        );
        MainHomeInteractive::ConfigureInteractionBinding(InteractionBinding);
        bInteractionKeyBound = true;
    }
}

void AMainHomeInteractiveActor::DeactivateCurrentInput()
{
    if (APawn* Pawn = InputPawn.Get())
    {
        Pawn->OnDestroyed.RemoveDynamic(
            this,
            &AMainHomeInteractiveActor::HandleInputPawnDestroyed
        );
    }
    RemoveInteractionBinding();
    if (APlayerController* Controller = InputController.Get())
    {
        DisableInput(Controller);
    }
    InputPawn.Reset();
    InputController.Reset();
}

void AMainHomeInteractiveActor::HandleInputPawnDestroyed(AActor* DestroyedActor)
{
    APawn* DestroyedPawn = Cast<APawn>(DestroyedActor);
    if (DestroyedPawn == nullptr || InputPawn.Get() != DestroyedPawn)
    {
        return;
    }

    LocalPawnOverlapCounts.Remove(DestroyedPawn);
    DeactivateCurrentInput();
    for (const TPair<TWeakObjectPtr<APawn>, int32>& Pair : LocalPawnOverlapCounts)
    {
        if (Pair.Value > 0 && Pair.Key.IsValid())
        {
            ActivateInputForPawn(Pair.Key.Get());
            break;
        }
    }
}

void AMainHomeInteractiveActor::RemoveInteractionBinding()
{
    if (InputComponent != nullptr)
    {
        InputComponent->KeyBindings.RemoveAll(
            [this](const FInputKeyBinding& Binding)
            {
                return Binding.Chord.Key == EKeys::E
                    && Binding.KeyEvent == IE_Pressed
                    && Binding.KeyDelegate.IsBoundToObject(this);
            }
        );
    }
    bInteractionKeyBound = false;
}

void AMainHomeInteractiveActor::ApplyAnimationState()
{
    Shutter->SetRelativeScale3D(FVector(
        1.0f,
        1.0f,
        MainHomeInteractive::ComputeShutterScale(AnimationState.ShutterAlpha)
    ));
    Shutter->SetCollisionEnabled(
        MainHomeInteractive::ShouldEnableShutterCollision(
            AnimationState.ShutterAlpha,
            AnimationState.ShutterTarget
        )
            ? ECollisionEnabled::QueryAndPhysics
            : ECollisionEnabled::NoCollision
    );

    LeftHinge->SetRelativeRotation(FRotator(
        0.0f,
        MainHomeInteractive::ComputeDoorYaw(
            true,
            DoorOpenDirection,
            DoorAngleDegrees
        ) * AnimationState.LeftDoorAlpha,
        0.0f
    ));
    RightHinge->SetRelativeRotation(FRotator(
        0.0f,
        MainHomeInteractive::ComputeDoorYaw(
            false,
            DoorOpenDirection,
            DoorAngleDegrees
        ) * AnimationState.RightDoorAlpha,
        0.0f
    ));
}

void AMainHomeInteractiveActor::SetTickForAnimationState()
{
    SetActorTickEnabled(MainHomeInteractive::IsAnimationMoving(AnimationState));
}
