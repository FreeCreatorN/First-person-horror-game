using UnrealBuildTool;

public class MainHomeInteractive : ModuleRules
{
    public MainHomeInteractive(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(
            new[]
            {
                "Core",
                "CoreUObject",
                "Engine",
                "InputCore"
            }
        );
    }
}
