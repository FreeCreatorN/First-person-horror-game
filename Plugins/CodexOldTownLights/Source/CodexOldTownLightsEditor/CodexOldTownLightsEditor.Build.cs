using UnrealBuildTool;

public class CodexOldTownLightsEditor : ModuleRules
{
    public CodexOldTownLightsEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "CodexOldTownLights" });
        PrivateDependencyModuleNames.AddRange(new[] { "UnrealEd", "BlueprintGraph", "KismetCompiler", "Json" });
    }
}
