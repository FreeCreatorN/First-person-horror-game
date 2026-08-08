#if WITH_DEV_AUTOMATION_TESTS

#include "MainHomeInteractiveActor.h"

#include "Components/BoxComponent.h"
#include "Components/InputComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "InputCoreTypes.h"
#include "Misc/AutomationTest.h"
#include "PhysicsEngine/AggregateGeom.h"
#include "PhysicsEngine/BodySetup.h"
#include "UObject/Package.h"

using namespace MainHomeInteractive;

namespace
{
    struct FScopedMainHomeTestWorld
    {
        FScopedMainHomeTestWorld()
        {
            const FName WorldName = MakeUniqueObjectName(
                GetTransientPackage(),
                UWorld::StaticClass(),
                TEXT("MainHomeInteractionTestWorld")
            );
            World = NewObject<UWorld>(GetTransientPackage(), WorldName);
            World->WorldType = EWorldType::EditorPreview;

            FWorldContext& WorldContext = GEngine->CreateNewWorldContext(
                World->WorldType
            );
            WorldContext.SetCurrentWorld(World);
            World->InitializeNewWorld(UWorld::InitializationValues()
                .RequiresHitProxies(false)
                .ShouldSimulatePhysics(false)
                .EnableTraceCollision(true)
                .CreateNavigation(false)
                .CreateAISystem(false)
                .AllowAudioPlayback(false)
                .SetTransactional(false)
                .CreatePhysicsScene(true));
            FURL URL;
            World->InitializeActorsForPlay(URL);
        }

        ~FScopedMainHomeTestWorld()
        {
            GEngine->DestroyWorldContext(World);
            World->DestroyWorld(false);
        }

        UWorld* World = nullptr;
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FMainHomeDoorYawTest,
    "MainHomeInteractive.Door.MirroredYaw",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter
)

bool FMainHomeDoorYawTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("Left outward"), ComputeDoorYaw(true, EMainHomeDoorOpenDirection::Outward, 95.0f), -95.0f);
    TestEqual(TEXT("Right outward"), ComputeDoorYaw(false, EMainHomeDoorOpenDirection::Outward, 95.0f), 95.0f);
    TestEqual(TEXT("Left inward"), ComputeDoorYaw(true, EMainHomeDoorOpenDirection::Inward, 95.0f), 95.0f);
    TestEqual(TEXT("Right inward"), ComputeDoorYaw(false, EMainHomeDoorOpenDirection::Inward, 95.0f), -95.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FMainHomeIndependentDoorTargetsTest,
    "MainHomeInteractive.Door.IndependentTargets",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter
)

bool FMainHomeIndependentDoorTargetsTest::RunTest(const FString& Parameters)
{
    MainHomeInteractive::FAnimationState State;

    ToggleDoorTarget(State, true);
    TestEqual(TEXT("Left target opens"), State.LeftDoorTarget, 1.0f);
    TestEqual(TEXT("Right target remains closed"), State.RightDoorTarget, 0.0f);

    ToggleDoorTarget(State, false);
    TestEqual(TEXT("Left target remains open"), State.LeftDoorTarget, 1.0f);
    TestEqual(TEXT("Right target opens independently"), State.RightDoorTarget, 1.0f);

    ToggleDoorTarget(State, true);
    TestEqual(TEXT("Left target closes independently"), State.LeftDoorTarget, 0.0f);
    TestEqual(TEXT("Right target remains open"), State.RightDoorTarget, 1.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FMainHomeComponentLayoutResetTest,
    "MainHomeInteractive.Layout.ResetAfterMeshAssignment",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter
)

bool FMainHomeComponentLayoutResetTest::RunTest(const FString& Parameters)
{
    AMainHomeInteractiveActor* Actor = NewObject<AMainHomeInteractiveActor>();
    USceneComponent* Shutter = CastChecked<USceneComponent>(
        Actor->GetDefaultSubobjectByName(TEXT("Shutter"))
    );
    USceneComponent* LeftHinge = CastChecked<USceneComponent>(
        Actor->GetDefaultSubobjectByName(TEXT("LeftHinge"))
    );
    USceneComponent* LeftDoorLeaf = CastChecked<USceneComponent>(
        Actor->GetDefaultSubobjectByName(TEXT("LeftDoorLeaf"))
    );
    USceneComponent* RightHinge = CastChecked<USceneComponent>(
        Actor->GetDefaultSubobjectByName(TEXT("RightHinge"))
    );
    USceneComponent* RightDoorLeaf = CastChecked<USceneComponent>(
        Actor->GetDefaultSubobjectByName(TEXT("RightDoorLeaf"))
    );
    UBoxComponent* ShutterZone = CastChecked<UBoxComponent>(
        Actor->GetDefaultSubobjectByName(TEXT("ShutterInteractionZone"))
    );

    const FTransform StaleOverride(
        FRotator(7.0f, 11.0f, 13.0f),
        FVector(17.0f, 19.0f, 23.0f),
        FVector(2.0f, 3.0f, 4.0f)
    );
    Shutter->SetRelativeTransform(StaleOverride);
    LeftHinge->SetRelativeTransform(StaleOverride);
    LeftDoorLeaf->SetRelativeTransform(StaleOverride);
    RightHinge->SetRelativeTransform(StaleOverride);
    RightDoorLeaf->SetRelativeTransform(StaleOverride);
    ShutterZone->SetRelativeTransform(StaleOverride);
    ShutterZone->SetBoxExtent(FVector(999.0f));

    Actor->SetMainHomeMeshes(nullptr, nullptr, nullptr, nullptr);

    TestEqual(TEXT("Shutter pivot is restored"), Shutter->GetRelativeLocation(), FVector(-96.0f, -394.5f, 277.0f));
    TestTrue(TEXT("Shutter has identity rotation and scale"), Shutter->GetRelativeTransform().GetRotation().IsIdentity() && Shutter->GetRelativeScale3D().Equals(FVector::OneVector));
    TestEqual(TEXT("Left hinge pivot is restored"), LeftHinge->GetRelativeLocation(), FVector(76.0f, -394.0f, 121.0f));
    TestTrue(TEXT("Left hinge has identity rotation and scale"), LeftHinge->GetRelativeTransform().GetRotation().IsIdentity() && LeftHinge->GetRelativeScale3D().Equals(FVector::OneVector));
    TestTrue(TEXT("Left leaf relative transform is identity"), LeftDoorLeaf->GetRelativeTransform().Equals(FTransform::Identity));
    TestEqual(TEXT("Right hinge pivot is restored"), RightHinge->GetRelativeLocation(), FVector(212.0f, -394.0f, 121.0f));
    TestTrue(TEXT("Right hinge has identity rotation and scale"), RightHinge->GetRelativeTransform().GetRotation().IsIdentity() && RightHinge->GetRelativeScale3D().Equals(FVector::OneVector));
    TestTrue(TEXT("Right leaf relative transform is identity"), RightDoorLeaf->GetRelativeTransform().Equals(FTransform::Identity));
    TestEqual(TEXT("Two-sided shutter zone location is restored"), ShutterZone->GetRelativeLocation(), FVector(-96.0f, -394.5f, 151.0f));
    TestEqual(TEXT("Two-sided shutter zone extent is restored"), ShutterZone->GetUnscaledBoxExtent(), FVector(125.0f, 350.0f, 150.0f));

    const FBox ShutterZoneBounds(
        ShutterZone->GetRelativeLocation() - ShutterZone->GetUnscaledBoxExtent(),
        ShutterZone->GetRelativeLocation() + ShutterZone->GetUnscaledBoxExtent()
    );
    TestTrue(
        TEXT("Shutter zone includes an exterior interaction point"),
        ShutterZoneBounds.IsInsideOrOn(FVector(-96.0f, -690.0f, 151.0f))
    );
    TestTrue(
        TEXT("Shutter zone includes an interior interaction point"),
        ShutterZoneBounds.IsInsideOrOn(FVector(-96.0f, -100.0f, 151.0f))
    );
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FMainHomeShutterScaleAndCollisionTest,
    "MainHomeInteractive.Shutter.ScaleAndEndpointCollision",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter
)

bool FMainHomeShutterScaleAndCollisionTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("Closed Z scale"), ComputeShutterScale(0.0f), 1.0f);
    TestEqual(TEXT("Open Z scale"), ComputeShutterScale(1.0f), 0.12f);
    TestTrue(TEXT("Open shutter retains 31.56 cm strip"), FMath::IsNearlyEqual(263.0f * ComputeShutterScale(1.0f), 31.56f, 0.01f));
    TestTrue(TEXT("Open shutter clears 231.44 cm"), FMath::IsNearlyEqual(263.0f * (1.0f - ComputeShutterScale(1.0f)), 231.44f, 0.01f));
    TestEqual(TEXT("Collision stays physical while opening"), GetShutterCollisionMode(0.99f, 1.0f), ECollisionEnabled::QueryAndPhysics);
    TestEqual(TEXT("Fully-open strip remains traceable"), GetShutterCollisionMode(1.0f, 1.0f), ECollisionEnabled::QueryOnly);
    TestEqual(TEXT("Collision becomes physical before closing"), GetShutterCollisionMode(1.0f, 0.0f), ECollisionEnabled::QueryAndPhysics);

    MainHomeInteractive::FAnimationState State;
    State.ShutterAlpha = 1.0f;
    State.ShutterTarget = 1.0f;
    ToggleShutterTarget(State);
    TestEqual(TEXT("Fully-open shutter targets closing after E"), State.ShutterTarget, 0.0f);
    TestEqual(
        TEXT("Closing target immediately restores shutter collision"),
        GetShutterCollisionMode(State.ShutterAlpha, State.ShutterTarget),
        ECollisionEnabled::QueryAndPhysics
    );
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FMainHomeHitClassificationTest,
    "MainHomeInteractive.Input.HitClassification",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter
)

bool FMainHomeHitClassificationTest::RunTest(const FString& Parameters)
{
    UStaticMeshComponent* Shutter = NewObject<UStaticMeshComponent>();
    UStaticMeshComponent* LeftDoor = NewObject<UStaticMeshComponent>();
    UStaticMeshComponent* RightDoor = NewObject<UStaticMeshComponent>();
    UStaticMeshComponent* Foreign = NewObject<UStaticMeshComponent>();

    TestEqual(TEXT("Shutter hit"), ClassifyHitComponent(Shutter, Shutter, LeftDoor, RightDoor), EHitPart::Shutter);
    TestEqual(TEXT("Left leaf hit"), ClassifyHitComponent(LeftDoor, Shutter, LeftDoor, RightDoor), EHitPart::LeftDoor);
    TestEqual(TEXT("Right leaf hit"), ClassifyHitComponent(RightDoor, Shutter, LeftDoor, RightDoor), EHitPart::RightDoor);
    TestEqual(TEXT("Foreign component ignored"), ClassifyHitComponent(Foreign, Shutter, LeftDoor, RightDoor), EHitPart::None);
    TestEqual(TEXT("Null component ignored"), ClassifyHitComponent(nullptr, Shutter, LeftDoor, RightDoor), EHitPart::None);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FMainHomeProductionGeometryAndTraceTest,
    "MainHomeInteractive.Integration.GeometryAndTrace",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter
)

bool FMainHomeProductionGeometryAndTraceTest::RunTest(
    const FString& Parameters
)
{
    FScopedMainHomeTestWorld TestWorld;
    AMainHomeInteractiveActor* Actor =
        TestWorld.World->SpawnActor<AMainHomeInteractiveActor>();
    if (!TestNotNull(TEXT("Interactive actor spawns"), Actor))
    {
        return false;
    }

    UStaticMeshComponent* Shutter = CastChecked<UStaticMeshComponent>(
        Actor->GetDefaultSubobjectByName(TEXT("Shutter"))
    );
    UStaticMeshComponent* LeftDoor = CastChecked<UStaticMeshComponent>(
        Actor->GetDefaultSubobjectByName(TEXT("LeftDoorLeaf"))
    );
    UStaticMeshComponent* RightDoor = CastChecked<UStaticMeshComponent>(
        Actor->GetDefaultSubobjectByName(TEXT("RightDoorLeaf"))
    );
    UStaticMesh* ShutterMesh = Shutter->GetStaticMesh().Get();
    UStaticMesh* LeftMesh = LeftDoor->GetStaticMesh().Get();
    UStaticMesh* RightMesh = RightDoor->GetStaticMesh().Get();
    if (!TestNotNull(TEXT("Shutter mesh is assigned"), ShutterMesh)
        || !TestNotNull(TEXT("Left mesh is assigned"), LeftMesh)
        || !TestNotNull(TEXT("Right mesh is assigned"), RightMesh))
    {
        return false;
    }

    TestEqual(
        TEXT("Left component owns left asset"),
        LeftMesh->GetName(),
        FString(TEXT("SM_MainHome_Door_Left"))
    );
    TestEqual(
        TEXT("Right component owns right asset"),
        RightMesh->GetName(),
        FString(TEXT("SM_MainHome_Door_Right"))
    );

    const FBox LeftVisualWorldBounds = LeftMesh->GetBoundingBox().TransformBy(
        LeftDoor->GetComponentTransform()
    );
    const FBox RightVisualWorldBounds = RightMesh->GetBoundingBox().TransformBy(
        RightDoor->GetComponentTransform()
    );

    const UBodySetup* LeftBodySetup = LeftMesh->GetBodySetup();
    const UBodySetup* RightBodySetup = RightMesh->GetBodySetup();
    if (!TestNotNull(TEXT("Left collision body exists"), LeftBodySetup)
        || !TestNotNull(TEXT("Right collision body exists"), RightBodySetup))
    {
        return false;
    }
    if (!TestEqual(
            TEXT("Left leaf has one aligned collision box"),
            LeftBodySetup->AggGeom.BoxElems.Num(),
            1
        )
        || !TestEqual(
            TEXT("Right leaf has one aligned collision box"),
            RightBodySetup->AggGeom.BoxElems.Num(),
            1
        ))
    {
        return false;
    }

    const FKBoxElem& LeftCollisionBox =
        LeftBodySetup->AggGeom.BoxElems[0];
    const FKBoxElem& RightCollisionBox =
        RightBodySetup->AggGeom.BoxElems[0];
    const FVector LeftCollisionExtent(
        LeftCollisionBox.X * 0.5f,
        LeftCollisionBox.Y * 0.5f,
        LeftCollisionBox.Z * 0.5f
    );
    const FVector RightCollisionExtent(
        RightCollisionBox.X * 0.5f,
        RightCollisionBox.Y * 0.5f,
        RightCollisionBox.Z * 0.5f
    );
    const FBox LeftCollisionWorldBounds(
        LeftCollisionBox.Center - LeftCollisionExtent,
        LeftCollisionBox.Center + LeftCollisionExtent
    );
    const FBox RightCollisionWorldBounds(
        RightCollisionBox.Center - RightCollisionExtent,
        RightCollisionBox.Center + RightCollisionExtent
    );
    const FBox LeftWorldBounds = LeftCollisionWorldBounds.TransformBy(
        LeftDoor->GetComponentTransform()
    );
    const FBox RightWorldBounds = RightCollisionWorldBounds.TransformBy(
        RightDoor->GetComponentTransform()
    );

    TestTrue(
        TEXT("Left collision leaf hides under left frame"),
        FMath::IsNearlyEqual(LeftWorldBounds.Min.X, 75.0f, 0.01f)
    );
    TestTrue(
        TEXT("Right collision leaf hides under right frame"),
        FMath::IsNearlyEqual(RightWorldBounds.Max.X, 213.0f, 0.01f)
    );
    TestTrue(
        TEXT("Center division is unchanged"),
        FMath::IsNearlyEqual(
            RightWorldBounds.Min.X - LeftWorldBounds.Max.X,
            0.5f,
            0.01f
        )
    );
    TestTrue(
        TEXT("Detailed visual leaves close the center seam"),
        RightVisualWorldBounds.Min.X - LeftVisualWorldBounds.Max.X <= 0.0f
    );
    TestTrue(
        TEXT("Detailed visual hardware remains outside collision proxies"),
        LeftVisualWorldBounds.Min.X <= LeftWorldBounds.Min.X
            && RightVisualWorldBounds.Max.X >= RightWorldBounds.Max.X
    );
    TestTrue(
        TEXT("Door vertical underlap is exact"),
        FMath::IsNearlyEqual(LeftWorldBounds.Min.Z, 14.0f, 0.01f)
            && FMath::IsNearlyEqual(
                LeftWorldBounds.Max.Z,
                228.0f,
                0.01f
            )
    );

    MainHomeInteractive::FAnimationState DoorState;
    TestTrue(
        TEXT("Actual left component dispatches"),
        ToggleTargetForHitPart(
            DoorState,
            ClassifyHitComponent(
                LeftDoor,
                Shutter,
                LeftDoor,
                RightDoor
            )
        )
    );
    TestEqual(TEXT("Left target opens"), DoorState.LeftDoorTarget, 1.0f);
    TestEqual(
        TEXT("Right target stays closed"),
        DoorState.RightDoorTarget,
        0.0f
    );

    Shutter->SetRelativeScale3D(FVector(1.0f, 1.0f, 0.12f));
    Actor->ToggleShutter();
    Actor->Tick(10.0f);
    Shutter->UpdateComponentToWorld();
    TestWorld.World->UpdateWorldComponents(true, false);

    TestEqual(
        TEXT("Raised shutter keeps query collision for aiming"),
        Shutter->GetCollisionEnabled(),
        ECollisionEnabled::QueryOnly
    );
    TestEqual(
        TEXT("Raised shutter does not block the player capsule"),
        Shutter->GetCollisionResponseToChannel(ECC_Pawn),
        ECR_Ignore
    );
    TestEqual(
        TEXT("Raised shutter still blocks visibility traces"),
        Shutter->GetCollisionResponseToChannel(ECC_Visibility),
        ECR_Block
    );

    FHitResult Hit;
    const bool bHit = TestWorld.World->LineTraceSingleByChannel(
        Hit,
        FVector(-96.0f, -500.0f, 271.0f),
        FVector(-96.0f, -350.0f, 271.0f),
        ECC_Visibility
    );
    TestTrue(TEXT("Visibility trace hits raised top strip"), bHit);
    TestEqual(
        TEXT("Raised shutter is the first blocking component"),
        Hit.GetComponent(),
        static_cast<UPrimitiveComponent*>(Shutter)
    );

    FHitResult InteriorHit;
    const bool bInteriorHit = TestWorld.World->LineTraceSingleByChannel(
        InteriorHit,
        FVector(-96.0f, -100.0f, 250.0f),
        FVector(-96.0f, -450.0f, 250.0f),
        ECC_Visibility
    );
    TestTrue(TEXT("Interior trace reaches lower part of raised strip"), bInteriorHit);
    TestEqual(
        TEXT("Raised shutter is first blocking component from inside"),
        InteriorHit.GetComponent(),
        static_cast<UPrimitiveComponent*>(Shutter)
    );

    MainHomeInteractive::FAnimationState ShutterState;
    ShutterState.ShutterAlpha = 1.0f;
    ShutterState.ShutterTarget = 1.0f;
    TestTrue(
        TEXT("Actual traced strip dispatches"),
        ToggleTargetForHitPart(
            ShutterState,
            ClassifyHitComponent(
                Hit.GetComponent(),
                Shutter,
                LeftDoor,
                RightDoor
            )
        )
    );
    TestEqual(
        TEXT("Aimed raised strip targets closing"),
        ShutterState.ShutterTarget,
        0.0f
    );

    Actor->ToggleShutter();
    Actor->Tick(10.0f);
    TestEqual(
        TEXT("Closed shutter restores player blocking"),
        Shutter->GetCollisionResponseToChannel(ECC_Pawn),
        ECR_Block
    );
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FMainHomeShutterCloseRequiresAimTest,
    "MainHomeInteractive.Input.ShutterCloseRequiresAim",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter
)

bool FMainHomeShutterCloseRequiresAimTest::RunTest(const FString& Parameters)
{
    MainHomeInteractive::FAnimationState State;
    State.ShutterTarget = 1.0f;
    UStaticMeshComponent* Shutter = NewObject<UStaticMeshComponent>();
    UStaticMeshComponent* LeftDoor = NewObject<UStaticMeshComponent>();
    UStaticMeshComponent* RightDoor = NewObject<UStaticMeshComponent>();

    const EHitPart Miss = ClassifyHitComponent(
        nullptr,
        Shutter,
        LeftDoor,
        RightDoor
    );
    if (Miss == EHitPart::Shutter)
    {
        ToggleShutterTarget(State);
    }
    TestEqual(TEXT("Missing the top strip leaves shutter open"), State.ShutterTarget, 1.0f);

    const EHitPart ShutterHit = ClassifyHitComponent(
        Shutter,
        Shutter,
        LeftDoor,
        RightDoor
    );
    if (ShutterHit == EHitPart::Shutter)
    {
        ToggleShutterTarget(State);
    }
    TestEqual(TEXT("Aiming at the top strip targets closing"), State.ShutterTarget, 0.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FMainHomeInteractionBindingTest,
    "MainHomeInteractive.Input.NonConsumingBinding",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter
)

bool FMainHomeInteractionBindingTest::RunTest(const FString& Parameters)
{
    FInputKeyBinding Binding(FInputChord(EKeys::E), IE_Pressed);
    TestTrue(TEXT("Input binding consumes by default"), Binding.bConsumeInput);

    ConfigureInteractionBinding(Binding);

    TestFalse(TEXT("Main Home interaction binding does not consume E"), Binding.bConsumeInput);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FMainHomeTickShutdownTest,
    "MainHomeInteractive.Animation.TickShutdown",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter
)

bool FMainHomeTickShutdownTest::RunTest(const FString& Parameters)
{
    MainHomeInteractive::FAnimationState State;
    TestFalse(TEXT("Settled closed state does not tick"), IsAnimationMoving(State));

    State.LeftDoorTarget = 1.0f;
    TestTrue(TEXT("Changing one target requires tick"), IsAnimationMoving(State));

    State.LeftDoorAlpha = AdvanceAlpha(State.LeftDoorAlpha, State.LeftDoorTarget, 0.5f, 0.5f);
    TestEqual(TEXT("Alpha reaches its target"), State.LeftDoorAlpha, 1.0f);
    TestFalse(TEXT("All settled states shut tick down"), IsAnimationMoving(State));
    return true;
}

#endif
