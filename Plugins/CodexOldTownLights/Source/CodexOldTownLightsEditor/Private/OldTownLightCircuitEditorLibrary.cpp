#include "OldTownLightCircuitEditorLibrary.h"

#include "OldTownLightCircuitActor.h"
#include "Components/LightComponent.h"
#include "Dom/JsonObject.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "K2Node_CallFunction.h"
#include "K2Node_Event.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_FunctionResult.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "KismetCompiler.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/PackageName.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UObjectIterator.h"

namespace
{
    const TCHAR* CircuitAssetPath = TEXT("/Game/CodexGenerated/OldTown/CallableLighting_20261016/Blueprints/BP_OTS_LightCircuit");
    const TCHAR* UserInterfacePath = TEXT("/Game/Yastar/Blueprints/BPI_Interact.BPI_Interact_C");

    UK2Node_CallFunction* AddCall(UEdGraph* Graph, const FName FunctionName)
    {
        UFunction* Function = AOldTownLightCircuitActor::StaticClass()->FindFunctionByName(FunctionName);
        if (!Function)
        {
            return nullptr;
        }
        UK2Node_CallFunction* Node = NewObject<UK2Node_CallFunction>(Graph);
        Node->CreateNewGuid();
        Node->SetFlags(RF_Transactional);
        Node->SetFromFunction(Function);
        Node->PostPlacedNewNode();
        Node->AllocateDefaultPins();
        Node->NodePosX = 400;
        Graph->AddNode(Node);
        return Node;
    }

    bool WireEvent(UBlueprint* Blueprint, UEdGraph* Graph, UClass* Interface,
        const FName EventName, const FName FunctionName, int32& PositionY,
        const TCHAR* BooleanDefault = nullptr)
    {
        UK2Node_Event* Event = FKismetEditorUtilities::AddDefaultEventNode(
            Blueprint, Graph, EventName, Interface, PositionY);
        UK2Node_CallFunction* Call = AddCall(Graph, FunctionName);
        if (!Event || !Call)
        {
            return false;
        }
        Call->NodePosY = Event->NodePosY;
        Event->SetEnabledState(ENodeEnabledState::Enabled, true);
        const UEdGraphSchema_K2* Schema = GetDefault<UEdGraphSchema_K2>();
        if (!Schema->TryCreateConnection(Event->FindPin(UEdGraphSchema_K2::PN_Then),
            Call->FindPin(UEdGraphSchema_K2::PN_Execute)))
        {
            return false;
        }
        if (BooleanDefault)
        {
            UEdGraphPin* Pin = Call->FindPin(TEXT("bEnabled"));
            if (!Pin)
            {
                return false;
            }
            Schema->TrySetDefaultValue(*Pin, BooleanDefault);
        }
        return true;
    }
}

UBlueprint* UOldTownLightCircuitEditorLibrary::CreateCircuitBlueprint(const FString& AssetPath)
{
    if (AssetPath != CircuitAssetPath)
    {
        UE_LOG(LogTemp, Error, TEXT("OldTown circuit creation refused outside its fixed assistant-owned package: %s"), *AssetPath);
        return nullptr;
    }
    const FString ObjectPath = AssetPath + TEXT(".") + FPackageName::GetLongPackageAssetName(AssetPath);
    if (FPackageName::DoesPackageExist(AssetPath))
    {
        UBlueprint* Existing = LoadObject<UBlueprint>(nullptr, *ObjectPath);
        return Existing && Existing->ParentClass == AOldTownLightCircuitActor::StaticClass() ? Existing : nullptr;
    }

    UClass* Interface = LoadObject<UClass>(nullptr, UserInterfacePath);
    if (!Interface || !Interface->HasAnyClassFlags(CLASS_Interface))
    {
        UE_LOG(LogTemp, Error, TEXT("The read-only BPI_Interact interface could not be loaded."));
        return nullptr;
    }
    // Fail closed if the user's interface has changed; never edit or compile that asset here.
    for (const FName FunctionName : { FName(TEXT("Interact")), FName(TEXT("GetInteractText")),
        FName(TEXT("EnableHighlight")), FName(TEXT("DisableHighlight")) })
    {
        if (!Interface->FindFunctionByName(FunctionName))
        {
            UE_LOG(LogTemp, Error, TEXT("BPI_Interact no longer has expected function %s."), *FunctionName.ToString());
            return nullptr;
        }
    }
    UPackage* Package = CreatePackage(*AssetPath);
    UBlueprint* Blueprint = FKismetEditorUtilities::CreateBlueprint(
        AOldTownLightCircuitActor::StaticClass(), Package,
        FName(*FPackageName::GetLongPackageAssetName(AssetPath)), BPTYPE_Normal,
        UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
    if (!Blueprint || !FBlueprintEditorUtils::ImplementNewInterface(Blueprint, Interface->GetClassPathName()))
    {
        return nullptr;
    }
    UEdGraph* EventGraph = FBlueprintEditorUtils::FindEventGraph(Blueprint);
    if (!EventGraph)
    {
        EventGraph = FBlueprintEditorUtils::CreateNewGraph(Blueprint, TEXT("EventGraph"),
            UEdGraph::StaticClass(), UEdGraphSchema_K2::StaticClass());
        FBlueprintEditorUtils::AddUbergraphPage(Blueprint, EventGraph);
    }
    int32 PositionY = 0;
    if (!WireEvent(Blueprint, EventGraph, Interface, TEXT("Interact"), TEXT("ToggleLight"), PositionY) ||
        !WireEvent(Blueprint, EventGraph, Interface, TEXT("EnableHighlight"), TEXT("SetCircuitHighlight"), PositionY, TEXT("true")) ||
        !WireEvent(Blueprint, EventGraph, Interface, TEXT("DisableHighlight"), TEXT("SetCircuitHighlight"), PositionY, TEXT("false")))
    {
        return nullptr;
    }
    UEdGraph* TextGraph = nullptr;
    for (const FBPInterfaceDescription& Description : Blueprint->ImplementedInterfaces)
    {
        for (UEdGraph* Graph : Description.Graphs)
        {
            if (Graph && Graph->GetFName() == FName(TEXT("GetInteractText")))
            {
                TextGraph = Graph;
            }
        }
    }
    if (!TextGraph)
    {
        return nullptr;
    }
    UK2Node_FunctionEntry* Entry = nullptr;
    UK2Node_FunctionResult* Result = nullptr;
    for (UEdGraphNode* Node : TextGraph->Nodes)
    {
        if (UK2Node_FunctionEntry* Candidate = Cast<UK2Node_FunctionEntry>(Node)) { Entry = Candidate; }
        if (UK2Node_FunctionResult* Candidate = Cast<UK2Node_FunctionResult>(Node)) { Result = Candidate; }
    }
    UK2Node_CallFunction* GetText = AddCall(TextGraph, TEXT("GetCircuitInteractText"));
    const UEdGraphSchema_K2* Schema = GetDefault<UEdGraphSchema_K2>();
    if (!Entry || !Result || !GetText ||
        !Schema->TryCreateConnection(Entry->FindPin(UEdGraphSchema_K2::PN_Then), Result->FindPin(UEdGraphSchema_K2::PN_Execute)) ||
        !Schema->TryCreateConnection(GetText->FindPin(UEdGraphSchema_K2::PN_ReturnValue), Result->FindPin(TEXT("InteractText"))))
    {
        return nullptr;
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
    FCompilerResultsLog Results;
    FKismetEditorUtilities::CompileBlueprint(Blueprint, EBlueprintCompileOptions::None, &Results);
    if (Results.NumErrors > 0 || Blueprint->Status == BS_Error || !Blueprint->GeneratedClass ||
        !Blueprint->GeneratedClass->ImplementsInterface(Interface))
    {
        UE_LOG(LogTemp, Error, TEXT("The assistant circuit Blueprint failed compilation."));
        return nullptr;
    }
    FSavePackageArgs SaveArguments;
    SaveArguments.TopLevelFlags = RF_Public | RF_Standalone;
    SaveArguments.SaveFlags = SAVE_NoError;
    const FString Filename = FPackageName::LongPackageNameToFilename(AssetPath, FPackageName::GetAssetPackageExtension());
    return UPackage::SavePackage(Package, Blueprint, *Filename, SaveArguments) ? Blueprint : nullptr;
}

FString UOldTownLightCircuitEditorLibrary::InspectCircuit(AOldTownLightCircuitActor* Circuit)
{
    TSharedRef<FJsonObject> Record = MakeShared<FJsonObject>();
    Record->SetBoolField(TEXT("valid"), IsValid(Circuit));
    if (IsValid(Circuit))
    {
        Record->SetStringField(TEXT("actor"), Circuit->GetPathName());
        Record->SetStringField(TEXT("configuration_error"), Circuit->GetCircuitConfigurationError());
        Record->SetBoolField(TEXT("initialized"), Circuit->HasInitializedLightCircuit());
        Record->SetBoolField(TEXT("game_world"), Circuit->GetWorld() && Circuit->GetWorld()->IsGameWorld());
        Record->SetBoolField(TEXT("on"), Circuit->GetLightState());
        Record->SetNumberField(TEXT("level"), Circuit->GetLightLevel());
        Record->SetBoolField(TEXT("initially_on"), Circuit->bInitiallyOn);
        Record->SetStringField(TEXT("interact_text"), Circuit->GetInteractText().ToString());
        UMaterialInstanceDynamic* MID = Circuit->GetLampDynamicMaterial();
        Record->SetStringField(TEXT("mid"), MID ? MID->GetPathName() : FString());
        if (MID) { Record->SetNumberField(TEXT("light_strength"), MID->K2_GetScalarParameterValue(TEXT("LightStrength"))); }
        TArray<TSharedPtr<FJsonValue>> Lights;
        for (int32 Index = 0; Index < Circuit->ControlledLights.Num(); ++Index)
        {
            TSharedRef<FJsonObject> LightRecord = MakeShared<FJsonObject>();
            AActor* Actor = Circuit->ControlledLights[Index];
            LightRecord->SetStringField(TEXT("actor"), Actor ? Actor->GetPathName() : FString());
            if (ULightComponent* Light = AOldTownLightCircuitActor::GetAllowedLocalLightComponent(Actor))
            {
                LightRecord->SetNumberField(TEXT("intensity"), Light->Intensity);
                LightRecord->SetBoolField(TEXT("visible"), Light->IsVisible());
                LightRecord->SetBoolField(TEXT("hidden_in_game"), Light->bHiddenInGame);
                if (Circuit->BaseIntensities.IsValidIndex(Index))
                {
                    LightRecord->SetNumberField(TEXT("base_intensity"), Circuit->BaseIntensities[Index]);
                }
            }
            Lights.Add(MakeShared<FJsonValueObject>(LightRecord));
        }
        Record->SetArrayField(TEXT("lights"), Lights);
    }
    FString Result;
    FJsonSerializer::Serialize(Record, TJsonWriterFactory<>::Create(&Result));
    return Result;
}

void UOldTownLightCircuitEditorLibrary::RestoreAllEditorPreviews()
{
    for (TObjectIterator<AOldTownLightCircuitActor> It; It; ++It)
    {
        if (!It->IsTemplate() && It->GetWorld() && !It->GetWorld()->IsGameWorld())
        {
            It->RestoreEditorPreview();
        }
    }
}
