#include "Modules/ModuleManager.h"

#include "OldTownLightCircuitActor.h"
#include "Components/LightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Containers/Ticker.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/RectLight.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/DefaultValueHelper.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/StructOnScope.h"
#include "UObject/UnrealType.h"

namespace
{
    struct FValidationOptions
    {
        int32 ExpectedCircuitCount = 16;
        int32 ExpectedInitiallyOn = 13;
        FString Directory;
        FString SourceEvidenceFile;
        FString SourceEvidenceSHA1;
        TSharedPtr<FJsonObject> SourceEvidence;
        bool bCustomized = false;
    };

    // Validation is opt-in. No options are read and no report is written until
    // CodexOldTownLights.Validate is explicitly invoked.
    bool ValidateOutputPath(const FString& Directory, FString& Error)
    {
        const FString ProjectRoot = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir());
        FString Root = FPaths::Combine(ProjectRoot, TEXT("Saved/CodexOutputs"));
        FPaths::NormalizeDirectoryName(Root);
        if (FPaths::IsRelative(ProjectRoot) || !FPaths::CollapseRelativeDirectories(Root))
        {
            Error = TEXT("Unable to resolve the absolute project Saved/CodexOutputs directory.");
            return false;
        }
        if (Directory.Equals(Root, ESearchCase::IgnoreCase) || !FPaths::IsUnderDirectory(Directory, Root))
        {
            Error = TEXT("Validation output must be a child directory of project Saved/CodexOutputs.");
            return false;
        }
        IPlatformFile& Physical = FPlatformFileManager::Get().GetPlatformPhysical();
        // Inspect existing ancestors as well as the final file. On Windows this
        // rejects junctions and every FILE_ATTRIBUTE_REPARSE_POINT, not only links.
        FString Check = FPaths::Combine(Directory, TEXT("RuntimeValidation.json"));
        while (!Check.IsEmpty())
        {
            if (Physical.IsSymlink(*Check) != ESymlinkResult::NonSymlink)
            {
                Error = TEXT("Validation output may not traverse a symbolic link or junction.");
                return false;
            }
            const FString Parent = FPaths::GetPath(Check);
            if (Parent == Check) { break; }
            Check = Parent;
        }
        if (Physical.FileExists(*FPaths::Combine(Directory, TEXT("FinalReview.json"))))
        {
            Error = TEXT("An accepted evidence directory may not be overwritten by validation.");
            return false;
        }
        return true;
    }

    bool ReadValidationOptions(FValidationOptions& Options, FString& Error)
    {
        FString Count, InitiallyOn, Directory;
        const bool bCount = FParse::Value(FCommandLine::Get(), TEXT("CodexLightCircuitCount="), Count);
        const bool bInitiallyOn = FParse::Value(FCommandLine::Get(), TEXT("CodexLightInitiallyOn="), InitiallyOn);
        const bool bDirectory = FParse::Value(FCommandLine::Get(), TEXT("CodexLightValidationDir="), Directory);
        Options.bCustomized = bCount || bInitiallyOn || bDirectory;
        if ((bCount && !FDefaultValueHelper::ParseInt(Count, Options.ExpectedCircuitCount)) ||
            (bInitiallyOn && !FDefaultValueHelper::ParseInt(InitiallyOn, Options.ExpectedInitiallyOn)) ||
            Options.ExpectedCircuitCount < 1 || Options.ExpectedCircuitCount > 1024 ||
            Options.ExpectedInitiallyOn < 0 || Options.ExpectedInitiallyOn > Options.ExpectedCircuitCount)
        {
            Error = TEXT("Invalid light validation counts.");
            return false;
        }
        if (!bDirectory && (Options.ExpectedCircuitCount != 16 || Options.ExpectedInitiallyOn != 13))
        {
            Error = TEXT("Non-default counts require a separate CodexLightValidationDir.");
            return false;
        }
        if (!bDirectory) { Directory = TEXT("Saved/CodexOutputs/OldTownCallableLighting_20261016"); }
        if (Directory.IsEmpty())
        {
            Error = TEXT("CodexLightValidationDir may not be empty.");
            return false;
        }
        const FString ProjectRoot = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir());
        if (FPaths::IsRelative(ProjectRoot))
        {
            Error = TEXT("Unable to resolve the absolute project directory for validation.");
            return false;
        }
        Options.Directory = FPaths::ConvertRelativePathToFull(ProjectRoot, Directory);
        FPaths::NormalizeDirectoryName(Options.Directory);
        if (!FPaths::CollapseRelativeDirectories(Options.Directory))
        {
            Error = TEXT("Unable to collapse relative segments in CodexLightValidationDir.");
            return false;
        }
        if (!ValidateOutputPath(Options.Directory, Error))
        {
            return false;
        }
        Options.SourceEvidenceFile = FPaths::Combine(Options.Directory, TEXT("Applied.json"));
        TArray<uint8> Bytes;
        if (FFileHelper::LoadFileToArray(Bytes, *Options.SourceEvidenceFile))
        {
            FString SourceText;
            FFileHelper::BufferToString(SourceText, Bytes.GetData(), Bytes.Num());
            if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(SourceText), Options.SourceEvidence))
            {
                Error = TEXT("Validation source Applied.json is invalid JSON.");
                return false;
            }
            Options.SourceEvidenceSHA1 = FSHA1::HashBuffer(Bytes.GetData(), Bytes.Num()).ToString().ToLower();
        }
        else if (Options.bCustomized)
        {
            Error = TEXT("Customized validation requires Applied.json in the new evidence directory.");
            return false;
        }
        return true;
    }

    void AddValidationInputs(const TSharedRef<FJsonObject>& Report, const FValidationOptions& Options)
    {
        Report->SetNumberField(TEXT("expected_circuit_count"), Options.ExpectedCircuitCount);
        Report->SetNumberField(TEXT("expected_initial_on_count"), Options.ExpectedInitiallyOn);
        Report->SetNumberField(TEXT("expected_initial_off_count"), Options.ExpectedCircuitCount - Options.ExpectedInitiallyOn);
        Report->SetStringField(TEXT("validation_directory"), Options.Directory);
        Report->SetNumberField(TEXT("owned_process_id"), FPlatformProcess::GetCurrentProcessId());
        Report->SetBoolField(TEXT("customized_validation"), Options.bCustomized);
        Report->SetStringField(TEXT("source_evidence_file"), Options.SourceEvidenceFile);
        Report->SetStringField(TEXT("source_evidence_sha1"), Options.SourceEvidenceSHA1);
        if (Options.SourceEvidence) { Report->SetObjectField(TEXT("source_evidence"), Options.SourceEvidence); }
    }

    TSharedRef<FJsonObject> Observe(AOldTownLightCircuitActor* Circuit)
    {
        TSharedRef<FJsonObject> Result = MakeShared<FJsonObject>();
        Result->SetStringField(TEXT("actor"), Circuit->GetPathName());
        Result->SetBoolField(TEXT("has_begun_play"), Circuit->HasActorBegunPlay());
        Result->SetBoolField(TEXT("initialized"), Circuit->HasInitializedLightCircuit());
        Result->SetBoolField(TEXT("game_world"), Circuit->GetWorld() && Circuit->GetWorld()->IsGameWorld());
        Result->SetStringField(TEXT("configuration_error"), Circuit->GetCircuitConfigurationError());
        Result->SetBoolField(TEXT("initially_on"), Circuit->bInitiallyOn);
        Result->SetBoolField(TEXT("on"), Circuit->GetLightState());
        Result->SetNumberField(TEXT("level"), Circuit->GetLightLevel());
        Result->SetStringField(TEXT("interact_text"), Circuit->GetInteractText().ToString());
        UMaterialInstanceDynamic* MID = Circuit->GetLampDynamicMaterial();
        Result->SetStringField(TEXT("mid"), MID ? MID->GetPathName() : FString());
        Result->SetBoolField(TEXT("mid_transient"), MID && MID->HasAnyFlags(RF_Transient));
        if (MID)
        {
            Result->SetNumberField(TEXT("light_strength"), MID->K2_GetScalarParameterValue(TEXT("LightStrength")));
        }
        TArray<TSharedPtr<FJsonValue>> Lights;
        for (int32 Index = 0; Index < Circuit->ControlledLights.Num(); ++Index)
        {
            AActor* LightActor = Circuit->ControlledLights[Index];
            TSharedRef<FJsonObject> LightResult = MakeShared<FJsonObject>();
            LightResult->SetStringField(TEXT("actor"), LightActor ? LightActor->GetPathName() : FString());
            if (ULightComponent* Component = AOldTownLightCircuitActor::GetAllowedLocalLightComponent(LightActor))
            {
                LightResult->SetStringField(TEXT("class"), LightActor->GetClass()->GetPathName());
                LightResult->SetNumberField(TEXT("intensity"), Component->Intensity);
                LightResult->SetBoolField(TEXT("visible"), Component->IsVisible());
                LightResult->SetBoolField(TEXT("hidden_in_game"), Component->bHiddenInGame);
                LightResult->SetBoolField(TEXT("actor_hidden"), LightActor->IsHidden());
                if (Circuit->BaseIntensities.IsValidIndex(Index))
                {
                    LightResult->SetNumberField(TEXT("base_intensity"), Circuit->BaseIntensities[Index]);
                }
            }
            Lights.Add(MakeShared<FJsonValueObject>(LightResult));
        }
        Result->SetArrayField(TEXT("lights"), Lights);
        return Result;
    }

    bool CheckLevel(AOldTownLightCircuitActor* Circuit, const float Expected)
    {
        UMaterialInstanceDynamic* MID = Circuit->GetLampDynamicMaterial();
        bool bPassed = Circuit->HasActorBegunPlay() && Circuit->HasInitializedLightCircuit() &&
            Circuit->GetWorld() && Circuit->GetWorld()->IsGameWorld() && MID &&
            FMath::IsNearlyEqual(Circuit->GetLightLevel(), Expected) &&
            Circuit->GetLightState() == (Expected > 0.0f) &&
            FMath::IsNearlyEqual(MID->K2_GetScalarParameterValue(TEXT("LightStrength")), 20.0f * Expected, 0.001f);
        for (int32 Index = 0; Index < Circuit->ControlledLights.Num(); ++Index)
        {
            ULightComponent* Component = AOldTownLightCircuitActor::GetAllowedLocalLightComponent(Circuit->ControlledLights[Index]);
            bPassed &= Component && Circuit->BaseIntensities.IsValidIndex(Index);
            if (Component && Circuit->BaseIntensities.IsValidIndex(Index))
            {
                const float ExpectedIntensity = Circuit->BaseIntensities[Index] * Expected;
                bPassed &= FMath::IsNearlyEqual(Component->Intensity, ExpectedIntensity,
                    FMath::Max(0.0001f, ExpectedIntensity * 0.00001f));
                bPassed &= Component->IsVisible() == (Expected > 0.0f);
                bPassed &= Component->bHiddenInGame == (Expected <= 0.0f);
                bPassed &= !Circuit->ControlledLights[Index]->IsHidden();
            }
        }
        return bPassed && Circuit->GetCircuitConfigurationError().IsEmpty();
    }

    bool InvokeInterfaceEvent(AOldTownLightCircuitActor* Circuit, UClass* Interface, const FName FunctionName)
    {
        if (!Interface || !Circuit->GetClass()->ImplementsInterface(Interface))
        {
            return false;
        }
        UFunction* Function = Circuit->FindFunction(FunctionName);
        if (!Function || Function->ParmsSize != 0)
        {
            return false;
        }
        Circuit->ProcessEvent(Function, nullptr);
        return true;
    }

    bool CheckInterfaceText(AOldTownLightCircuitActor* Circuit, UClass* Interface, FString& Observed)
    {
        if (!Interface || !Circuit->GetClass()->ImplementsInterface(Interface))
        {
            return false;
        }
        UFunction* Function = Circuit->FindFunction(TEXT("GetInteractText"));
        FTextProperty* Output = Function ? FindFProperty<FTextProperty>(Function, TEXT("InteractText")) : nullptr;
        if (!Function || !Output)
        {
            return false;
        }
        FStructOnScope Parameters(Function);
        Circuit->ProcessEvent(Function, Parameters.GetStructMemory());
        Observed = Output->GetPropertyValue_InContainer(Parameters.GetStructMemory()).ToString();
        return Observed == Circuit->GetInteractText().ToString();
    }

    bool SaveReport(const TSharedRef<FJsonObject>& Report, const FValidationOptions& Options)
    {
        FString Error;
        if (!ValidateOutputPath(Options.Directory, Error))
        {
            UE_LOG(LogTemp, Error, TEXT("OldTown validation report refused: %s"), *Error);
            return false;
        }
        AddValidationInputs(Report, Options);
        bool bSourceUnchanged = true;
        if (Options.SourceEvidence)
        {
            TArray<uint8> Bytes;
            bSourceUnchanged = FFileHelper::LoadFileToArray(Bytes, *Options.SourceEvidenceFile) &&
                FSHA1::HashBuffer(Bytes.GetData(), Bytes.Num()).ToString().ToLower() == Options.SourceEvidenceSHA1;
        }
        Report->SetBoolField(TEXT("source_evidence_unchanged"), bSourceUnchanged);
        if (!bSourceUnchanged) { Report->SetBoolField(TEXT("passed"), false); }
        if (!IFileManager::Get().MakeDirectory(*Options.Directory, true)) { return false; }
        FString Text;
        FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Text));
        const bool bSaved = FFileHelper::SaveStringToFile(Text,
            *FPaths::Combine(Options.Directory, TEXT("RuntimeValidation.json")),
            FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        return bSaved && bSourceUnchanged;
    }

    bool ValidateBeforeBeginPlay(UWorld* World, AOldTownLightCircuitActor* Source,
        const TSharedRef<FJsonObject>& Report)
    {
        bool bPassed = true;
        TArray<TSharedPtr<FJsonValue>> Cases;
        FActorSpawnParameters Parameters;
        Parameters.ObjectFlags |= RF_Transient;
        Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        const FVector Position(0.0f, 0.0f, -100000.0f);
        const FTransform Transform(Position);
        for (const bool InitiallyOn : {false, true})
        {
            for (const float Requested : {0.0f, 0.5f, 1.0f})
            {
                AStaticMeshActor* Lamp = World->SpawnActor<AStaticMeshActor>(Position, FRotator::ZeroRotator, Parameters);
                ARectLight* Light = World->SpawnActor<ARectLight>(Position, FRotator::ZeroRotator, Parameters);
                AOldTownLightCircuitActor* Circuit = World->SpawnActorDeferred<AOldTownLightCircuitActor>(
                    Source->GetClass(), Transform, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
                TSharedRef<FJsonObject> Case = MakeShared<FJsonObject>();
                bool bCasePassed = Lamp && Light && Circuit;
                if (bCasePassed)
                {
                    Lamp->SetActorHiddenInGame(true);
                    UStaticMeshComponent* Mesh = Lamp->GetStaticMeshComponent();
                    Mesh->SetMobility(EComponentMobility::Movable);
                    Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
                    Mesh->SetStaticMesh(Source->TargetLampMesh->GetStaticMeshComponent()->GetStaticMesh());
                    Mesh->SetMaterial(2, Source->GetLampDynamicMaterial()->Parent);
                    Circuit->SetFlags(RF_Transient);
                    Circuit->TargetLampMesh = Lamp;
                    Circuit->EmissiveMaterialSlot = 2;
                    Circuit->ControlledLights.Add(Light);
                    Circuit->BaseIntensities.Add(100.0f);
                    Circuit->bInitiallyOn = InitiallyOn;
                    bCasePassed &= !Circuit->HasActorBegunPlay();
                    Circuit->SetLightLevel(Requested);
                    Circuit->FinishSpawning(Transform);
                    bCasePassed &= CheckLevel(Circuit, Requested);
                    Case->SetObjectField(TEXT("after_begin_play"), Observe(Circuit));
                }
                if (Circuit) { Circuit->Destroy(); }
                if (Light) { Light->Destroy(); }
                if (Lamp) { Lamp->Destroy(); }
                Case->SetBoolField(TEXT("initially_on"), InitiallyOn);
                Case->SetNumberField(TEXT("requested_before_begin_play"), Requested);
                Case->SetBoolField(TEXT("passed"), bCasePassed);
                Cases.Add(MakeShared<FJsonValueObject>(Case));
                bPassed &= bCasePassed;
            }
        }
        Report->SetArrayField(TEXT("before_begin_play_cases"), Cases);
        Report->SetBoolField(TEXT("before_begin_play_calls_preserved"), bPassed);
        return bPassed;
    }

    bool ValidateWorld(UWorld* World, const FValidationOptions& Options)
    {
        TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
        Report->SetStringField(TEXT("world"), World->GetOutermost()->GetName());
        Report->SetBoolField(TEXT("game_world"), World->IsGameWorld());
        Report->SetBoolField(TEXT("world_begun_play"), World->HasBegunPlay());
        Report->SetBoolField(TEXT("no_asset_save_called"), true);
        Report->SetStringField(TEXT("verification"), TEXT("Real GameWorld BeginPlay plus direct Blueprint interface ProcessEvent and actual MID/light component reads."));
        TArray<AOldTownLightCircuitActor*> Circuits;
        for (TActorIterator<AOldTownLightCircuitActor> It(World); It; ++It) { Circuits.Add(*It); }
        Circuits.Sort([](const AOldTownLightCircuitActor& Left, const AOldTownLightCircuitActor& Right)
            { return Left.GetPathName() < Right.GetPathName(); });
        Report->SetNumberField(TEXT("circuit_count"), Circuits.Num());
        bool bPassed = World->IsGameWorld() && World->HasBegunPlay() && Circuits.Num() == Options.ExpectedCircuitCount;
        if (Options.SourceEvidence)
        {
            FString SourceWorld;
            bool bSourcePassed = false;
            const bool bSourceMatches = Options.SourceEvidence->TryGetStringField(TEXT("target_level"), SourceWorld) &&
                SourceWorld == World->GetOutermost()->GetName() &&
                Options.SourceEvidence->TryGetBoolField(TEXT("passed"), bSourcePassed) && bSourcePassed;
            Report->SetBoolField(TEXT("source_evidence_world_matches"), bSourceMatches);
            bPassed &= bSourceMatches;
        }
        UClass* Interface = LoadObject<UClass>(nullptr, TEXT("/Game/Yastar/Blueprints/BPI_Interact.BPI_Interact_C"));
        TSet<UMaterialInstanceDynamic*> UniqueMIDs;
        TSet<AActor*> UniqueLightActors;
        TSet<AActor*> UniqueLampActors;
        int32 InitialOnCount = 0;
        int32 InitialOffCount = 0;
        TArray<TSharedPtr<FJsonValue>> Records;
        TArray<float> StartingLevels;
        for (AOldTownLightCircuitActor* Circuit : Circuits) { StartingLevels.Add(Circuit->GetLightLevel()); }

        for (int32 CircuitIndex = 0; CircuitIndex < Circuits.Num(); ++CircuitIndex)
        {
            AOldTownLightCircuitActor* Circuit = Circuits[CircuitIndex];
            TSharedRef<FJsonObject> Record = MakeShared<FJsonObject>();
            Record->SetObjectField(TEXT("initial"), Observe(Circuit));
            Circuit->bInitiallyOn ? ++InitialOnCount : ++InitialOffCount;
            bool bCircuitPassed = CheckLevel(Circuit, Circuit->bInitiallyOn ? 1.0f : 0.0f);
            bCircuitPassed &= Circuit->ControlledLights.Num() == 1 && Circuit->BaseIntensities.Num() == 1;
            Record->SetBoolField(TEXT("exactly_one_real_light"), Circuit->ControlledLights.Num() == 1);
            UMaterialInstanceDynamic* MID = Circuit->GetLampDynamicMaterial();
            const bool bUniqueMID = MID && !UniqueMIDs.Contains(MID);
            bCircuitPassed &= bUniqueMID;
            UniqueMIDs.Add(MID);
            Record->SetBoolField(TEXT("unique_mid"), bUniqueMID);
            const bool bUniqueLamp = Circuit->TargetLampMesh && !UniqueLampActors.Contains(Circuit->TargetLampMesh);
            bCircuitPassed &= bUniqueLamp;
            UniqueLampActors.Add(Circuit->TargetLampMesh);
            for (AActor* Light : Circuit->ControlledLights)
            {
                bCircuitPassed &= !UniqueLightActors.Contains(Light);
                UniqueLightActors.Add(Light);
            }
            TArray<TSharedPtr<FJsonValue>> Steps;
            auto AddStep = [&](const TCHAR* Name, const float Expected)
            {
                TSharedRef<FJsonObject> Step = Observe(Circuit);
                Step->SetStringField(TEXT("step"), Name);
                Step->SetNumberField(TEXT("expected_level"), Expected);
                bool bStepPassed = CheckLevel(Circuit, Expected);
                FString InterfaceText;
                bStepPassed &= CheckInterfaceText(Circuit, Interface, InterfaceText);
                Step->SetStringField(TEXT("interface_interact_text"), InterfaceText);
                // Read other real MID/light states as well as logical controller state.
                bool bOtherCircuitsUnchanged = true;
                for (int32 OtherIndex = 0; OtherIndex < Circuits.Num(); ++OtherIndex)
                {
                    if (OtherIndex != CircuitIndex)
                    {
                        bOtherCircuitsUnchanged &= CheckLevel(Circuits[OtherIndex], StartingLevels[OtherIndex]);
                    }
                }
                bStepPassed &= bOtherCircuitsUnchanged;
                Step->SetBoolField(TEXT("other_circuits_unchanged"), bOtherCircuitsUnchanged);
                Step->SetBoolField(TEXT("passed"), bStepPassed);
                Steps.Add(MakeShared<FJsonValueObject>(Step));
                bCircuitPassed &= bStepPassed;
            };
            Circuit->SetLightOn(false); AddStep(TEXT("off"), 0.0f);
            Circuit->SetLightLevel(0.5f); AddStep(TEXT("half"), 0.5f);
            Circuit->SetLightOn(true); AddStep(TEXT("on"), 1.0f);
            Circuit->SetLightOn(true); AddStep(TEXT("repeated_on"), 1.0f);
            Circuit->ToggleLight(); AddStep(TEXT("toggle_off"), 0.0f);
            Circuit->ToggleLight(); AddStep(TEXT("toggle_on"), 1.0f);
            bCircuitPassed &= InvokeInterfaceEvent(Circuit, Interface, TEXT("Interact"));
            AddStep(TEXT("interface_off"), 0.0f);
            bCircuitPassed &= InvokeInterfaceEvent(Circuit, Interface, TEXT("Interact"));
            AddStep(TEXT("interface_on"), 1.0f);
            Circuit->SetLightLevel(StartingLevels[CircuitIndex]);
            AddStep(TEXT("restored_initial"), StartingLevels[CircuitIndex]);
            Record->SetArrayField(TEXT("steps"), Steps);
            Record->SetBoolField(TEXT("passed"), bCircuitPassed);
            Records.Add(MakeShared<FJsonValueObject>(Record));
            bPassed &= bCircuitPassed;
        }
        Report->SetNumberField(TEXT("initial_on_count"), InitialOnCount);
        Report->SetNumberField(TEXT("initial_off_count"), InitialOffCount);
        Report->SetNumberField(TEXT("unique_mid_count"), UniqueMIDs.Num());
        Report->SetNumberField(TEXT("unique_local_light_count"), UniqueLightActors.Num());
        Report->SetNumberField(TEXT("unique_lamp_count"), UniqueLampActors.Num());
        Report->SetArrayField(TEXT("circuits"), Records);
        bPassed &= InitialOnCount == Options.ExpectedInitiallyOn &&
            InitialOffCount == Options.ExpectedCircuitCount - Options.ExpectedInitiallyOn &&
            UniqueMIDs.Num() == Options.ExpectedCircuitCount &&
            UniqueLightActors.Num() == Options.ExpectedCircuitCount &&
            UniqueLampActors.Num() == Options.ExpectedCircuitCount;
        if (!Circuits.IsEmpty())
        {
            bPassed &= ValidateBeforeBeginPlay(World, Circuits[0], Report);
            for (int32 Index = 0; Index < Circuits.Num(); ++Index)
            {
                bPassed &= CheckLevel(Circuits[Index], StartingLevels[Index]);
            }
        }
        Report->SetBoolField(TEXT("passed"), bPassed);
        const bool bSaved = SaveReport(Report, Options);
        UE_LOG(LogTemp, Display, TEXT("OTS_LIGHT_RUNTIME_VALIDATION passed=%d saved=%d circuits=%d initial_on=%d initial_off=%d"),
            bPassed, bSaved, Circuits.Num(), InitialOnCount, InitialOffCount);
        return bPassed && bSaved;
    }
}

class FCodexOldTownLightsModule : public IModuleInterface
{
public:
    virtual void StartupModule() override
    {
        ValidationCommand = IConsoleManager::Get().RegisterConsoleCommand(
            TEXT("CodexOldTownLights.Validate"),
            TEXT("Validate old-town circuits in a real game world, write a JSON report, then exit with status."),
            FConsoleCommandWithWorldDelegate::CreateRaw(this, &FCodexOldTownLightsModule::StartValidation), ECVF_Default);
    }

    virtual void ShutdownModule() override
    {
        if (ValidationTicker.IsValid()) { FTSTicker::GetCoreTicker().RemoveTicker(ValidationTicker); }
        if (ValidationCommand) { IConsoleManager::Get().UnregisterConsoleObject(ValidationCommand); }
    }

private:
    IConsoleObject* ValidationCommand = nullptr;
    FTSTicker::FDelegateHandle ValidationTicker;
    bool bValidationRequested = false;

    void StartValidation(UWorld* RequestedWorld)
    {
        if (bValidationRequested) { return; }
        bValidationRequested = true;
        FValidationOptions Options;
        FString OptionsError;
        if (!ReadValidationOptions(Options, OptionsError))
        {
            UE_LOG(LogTemp, Error, TEXT("OldTown validation refused: %s"), *OptionsError);
            FPlatformMisc::RequestExitWithStatus(false, 1);
            return;
        }
        const double StartTime = FPlatformTime::Seconds();
        const TWeakObjectPtr<UWorld> WeakWorld(RequestedWorld);
        ValidationTicker = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda(
            [WeakWorld, StartTime, Options](float)
            {
                UWorld* World = WeakWorld.Get();
                if ((!World || !World->IsGameWorld()) && GEngine)
                {
                    for (const FWorldContext& Context : GEngine->GetWorldContexts())
                    {
                        if (Context.World() && Context.World()->IsGameWorld()) { World = Context.World(); break; }
                    }
                }
                bool bReady = World && World->HasBegunPlay();
                if (bReady)
                {
                    int32 Count = 0;
                    for (TActorIterator<AOldTownLightCircuitActor> It(World); It; ++It)
                    {
                        ++Count;
                        bReady &= It->HasActorBegunPlay();
                    }
                    bReady &= Count > 0;
                }
                if (bReady)
                {
                    const bool bPassed = ValidateWorld(World, Options);
                    FPlatformMisc::RequestExitWithStatus(false, bPassed ? 0 : 1);
                    return false;
                }
                if (FPlatformTime::Seconds() - StartTime > 30.0)
                {
                    TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
                    Report->SetBoolField(TEXT("passed"), false);
                    Report->SetStringField(TEXT("error"), TEXT("No begun-play GameWorld with light circuits became available within 30 seconds."));
                    SaveReport(Report, Options);
                    FPlatformMisc::RequestExitWithStatus(false, 1);
                    return false;
                }
                return true;
            }), 0.1f);
    }
};

IMPLEMENT_MODULE(FCodexOldTownLightsModule, CodexOldTownLights)
