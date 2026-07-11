#if WITH_DEV_AUTOMATION_TESTS

#include "MainHomeInteractiveActor.h"

#include "Components/BoxComponent.h"
#include "Components/InputComponent.h"
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
    FMainHomeShutterScaleAndCollisionTest,
    "MainHomeInteractive.Shutter.ScaleAndEndpointCollision",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter
)

bool FMainHomeShutterScaleAndCollisionTest::RunTest(const FString& Parameters)
{
    TestEqual(TEXT("Closed Z scale"), ComputeShutterScale(0.0f), 1.0f);
    TestEqual(TEXT("Open Z scale"), ComputeShutterScale(1.0f), 0.03f);
    TestTrue(TEXT("Collision stays enabled while opening"), ShouldEnableShutterCollision(0.99f, 1.0f));
    TestFalse(TEXT("Collision disables only at fully-open endpoint"), ShouldEnableShutterCollision(1.0f, 1.0f));
    TestTrue(TEXT("Collision re-enables before closing"), ShouldEnableShutterCollision(1.0f, 0.0f));

    MainHomeInteractive::FAnimationState State;
    State.ShutterAlpha = 1.0f;
    State.ShutterTarget = 1.0f;
    ToggleShutterTarget(State);
    TestEqual(TEXT("Fully-open shutter targets closing after E"), State.ShutterTarget, 0.0f);
    TestTrue(
        TEXT("Closing target immediately restores shutter collision"),
        ShouldEnableShutterCollision(State.ShutterAlpha, State.ShutterTarget)
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
    UBoxComponent* ShutterTraceTarget = NewObject<UBoxComponent>();
    UStaticMeshComponent* LeftDoor = NewObject<UStaticMeshComponent>();
    UStaticMeshComponent* RightDoor = NewObject<UStaticMeshComponent>();
    UStaticMeshComponent* Foreign = NewObject<UStaticMeshComponent>();

    TestEqual(TEXT("Shutter hit"), ClassifyHitComponent(Shutter, Shutter, ShutterTraceTarget, LeftDoor, RightDoor), EHitPart::Shutter);
    TestEqual(TEXT("Shutter trace target hit"), ClassifyHitComponent(ShutterTraceTarget, Shutter, ShutterTraceTarget, LeftDoor, RightDoor), EHitPart::Shutter);
    TestEqual(TEXT("Left leaf hit"), ClassifyHitComponent(LeftDoor, Shutter, ShutterTraceTarget, LeftDoor, RightDoor), EHitPart::LeftDoor);
    TestEqual(TEXT("Right leaf hit"), ClassifyHitComponent(RightDoor, Shutter, ShutterTraceTarget, LeftDoor, RightDoor), EHitPart::RightDoor);
    TestEqual(TEXT("Foreign component ignored"), ClassifyHitComponent(Foreign, Shutter, ShutterTraceTarget, LeftDoor, RightDoor), EHitPart::None);
    TestEqual(TEXT("Null component ignored"), ClassifyHitComponent(nullptr, Shutter, ShutterTraceTarget, LeftDoor, RightDoor), EHitPart::None);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FMainHomeShutterTraceTargetBoundsTest,
    "MainHomeInteractive.Input.ShutterTraceTargetBounds",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter
)

bool FMainHomeShutterTraceTargetBoundsTest::RunTest(const FString& Parameters)
{
    const FVector Location = GetShutterTraceTargetLocation();
    const FVector Extent = GetShutterTraceTargetExtent();

    TestEqual(TEXT("Trace strip center X"), Location.X, -96.0);
    TestEqual(TEXT("Trace strip center Y"), Location.Y, -394.0);
    TestEqual(TEXT("Trace strip center Z"), Location.Z, 263.0);
    TestEqual(TEXT("Trace strip half-width"), Extent.X, 114.5);
    TestEqual(TEXT("Trace strip half-depth"), Extent.Y, 0.25);
    TestTrue(TEXT("Trace strip half-height stays at or below 3 cm"), Extent.Z <= 3.0f);
    TestTrue(TEXT("Trace strip bottom leaves the low sight channel open"), Location.Z - Extent.Z >= 260.0f);
    TestTrue(TEXT("Trace strip top remains below the fixed hood"), Location.Z + Extent.Z <= 266.0f);
    TestTrue(TEXT("Trace strip is inset from the shutter left edge"), Location.X - Extent.X > -211.0f);
    TestTrue(TEXT("Trace strip is inset from the shutter right edge"), Location.X + Extent.X < 19.0f);
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
