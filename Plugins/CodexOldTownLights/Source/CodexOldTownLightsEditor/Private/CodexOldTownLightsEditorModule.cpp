#include "Modules/ModuleManager.h"

#include "Editor.h"
#include "OldTownLightCircuitEditorLibrary.h"
#include "UObject/ObjectSaveContext.h"

class FCodexOldTownLightsEditorModule : public IModuleInterface
{
public:
    virtual void StartupModule() override
    {
        PreSaveHandle = FEditorDelegates::PreSaveWorldWithContext.AddLambda(
            [](UWorld*, FObjectPreSaveContext)
            {
                UOldTownLightCircuitEditorLibrary::RestoreAllEditorPreviews();
            });
        PrePIEHandle = FEditorDelegates::PreBeginPIE.AddLambda(
            [](bool)
            {
                UOldTownLightCircuitEditorLibrary::RestoreAllEditorPreviews();
            });
    }

    virtual void ShutdownModule() override
    {
        FEditorDelegates::PreSaveWorldWithContext.Remove(PreSaveHandle);
        FEditorDelegates::PreBeginPIE.Remove(PrePIEHandle);
        UOldTownLightCircuitEditorLibrary::RestoreAllEditorPreviews();
    }

private:
    FDelegateHandle PreSaveHandle;
    FDelegateHandle PrePIEHandle;
};

IMPLEMENT_MODULE(FCodexOldTownLightsEditorModule, CodexOldTownLightsEditor)
