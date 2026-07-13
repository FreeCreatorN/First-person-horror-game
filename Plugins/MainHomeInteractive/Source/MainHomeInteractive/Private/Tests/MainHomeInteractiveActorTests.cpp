#if WITH_DEV_AUTOMATION_TESTS

#include "MainHomeInteractiveActor.h"

#include "Components/BoxComponent.h"
#include "Components/InputComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "InputCoreTypes.h"
#include "Misc/AutomationTest.h"

using namespace MainHomeInteractive;

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
    TestEqual(TEXT("Left hinge pivot is restored"), LeftHinge->GetRelativeLocation(), FVector(78.0f, -394.0f, 120.0f));
    TestTrue(TEXT("Left hinge has identity rotation and scale"), LeftHinge->GetRelativeTransform().GetRotation().IsIdentity() && LeftHinge->GetRelativeScale3D().Equals(FVector::OneVector));
    TestTrue(TEXT("Left leaf relative transform is identity"), LeftDoorLeaf->GetRelativeTransform().Equals(FTransform::Identity));
    TestEqual(TEXT("Right hinge pivot is restored"), RightHinge->GetRelativeLocation(), FVector(210.0f, -394.0f, 120.0f));
    TestTrue(TEXT("Right hinge has identity rotation and scale"), RightHinge->GetRelativeTransform().GetRotation().IsIdentity() && RightHinge->GetRelativeScale3D().Equals(FVector::OneVector));
    TestTrue(TEXT("Right leaf relative transform is identity"), RightDoorLeaf->GetRelativeTransform().Equals(FTransform::Identity));
    TestEqual(TEXT("Compact shutter zone location is restored"), ShutterZone->GetRelativeLocation(), FVector(-96.0f, -430.0f, 151.0f));
    TestEqual(TEXT("Compact shutter zone extent is restored"), ShutterZone->GetUnscaledBoxExtent(), FVector(125.0f, 65.0f, 150.0f));
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
    TestEqual(TEXT("Open Z scale"), ComputeShutterScale(1.0f), 0.04f);
    TestTrue(TEXT("Open strip retains about 10 cm"), FMath::IsNearlyEqual(262.0f * ComputeShutterScale(1.0f), 10.48f, 0.01f));
    TestTrue(TEXT("Open shutter clears at least 250 cm"), FMath::IsNearlyEqual(262.0f * (1.0f - ComputeShutterScale(1.0f)), 251.52f, 0.01f));
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
