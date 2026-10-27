using UnrealBuildTool;
using System.IO;
public class CodexHotelAssetTools : ModuleRules
{
    public CodexHotelAssetTools(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });
        PrivateDependencyModuleNames.AddRange(new[] { "AssetTools", "Json" });
        PrivateIncludePaths.Add(Path.Combine(EngineDirectory, "Source/Developer/AssetTools/Internal"));
    }
}
