#pragma once

#include "CoreMinimal.h"
#include "Components/Widget.h"
#include "NotebookFlowTextWidget.h"
#include "NotebookFlowTextSlateWidget.generated.h"

class SNotebookFlowTextEditor;

//蓝图文字变化事件
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(
	FNotebookFlowTextSlateChanged,
	const FText&,
	NewText
);

UCLASS(BlueprintType,meta=(DisplayName="Notebook Flow Text Editor"))
class HORRORGAME_API UNotebookFlowTextSlateWidget : public UWidget
{
	GENERATED_BODY()

public:
    // 当前文字
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Notebook|Text")
    FText NotebookText;

    // 纸张尺寸
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Notebook|Layout")
    FVector2D PaperSize = FVector2D(700.0f, 1000.0f);

    // ==================== 文字样式 ====================

    // 字体大小
    UPROPERTY(EditAnywhere, BlueprintReadWrite,
        Category = "Notebook|Text Style",
        meta = (ClampMin = "6", ClampMax = "72"))
    int32 FontSize = 14;

    // 行高比例
    UPROPERTY(EditAnywhere, BlueprintReadWrite,
        Category = "Notebook|Text Style",
        meta = (ClampMin = "0.1", ClampMax = "3.0"))
    float LineHeightRatio = 1.4f;

    // 字间距
    UPROPERTY(EditAnywhere, BlueprintReadWrite,
        Category = "Notebook|Text Style",
        meta = (ClampMin = "-10", ClampMax = "100"))
    int32 LetterSpacing = 0;

    // 字体颜色
    UPROPERTY(EditAnywhere, BlueprintReadWrite,
        Category = "Notebook|Text Style")
    FColor FontColor = FColor(38, 38, 38, 255);

    // 笔记本实际横线间距
    UPROPERTY(EditAnywhere, BlueprintReadWrite,
        Category = "Notebook|Layout",
        meta = (ClampMin = "1.0"))
    float RuleSpacing = 30.0f;

    // 照片避让区域
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Notebook|Layout")
    TArray<FNotebookPhotoExclusionSquare> PhotoExclusionSquares;

    // 文字变化事件
    UPROPERTY(BlueprintAssignable, Category = "Notebook|Text")
    FNotebookFlowTextSlateChanged OnNotebookTextChanged;

    // 设置文字
    UFUNCTION(BlueprintCallable, Category = "Notebook|Text")
    void SetNotebookText(const FText& InText);

    // 获取文字
    UFUNCTION(BlueprintPure, Category = "Notebook|Text")
    FText GetNotebookText() const;

    // 更新照片避让区域
    UFUNCTION(BlueprintCallable, Category = "Notebook|Layout")
    void SetPhotoExclusionSquares(
        const TArray<FNotebookPhotoExclusionSquare>& InSquares
    );

    // 更新纸张布局
    UFUNCTION(BlueprintCallable, Category = "Notebook|Layout")
    void SetPaperLayout(
        FVector2D InPaperSize,
        float InRuleSpacing
    );

protected:

    virtual TSharedRef<SWidget> RebuildWidget() override;

    virtual void SynchronizeProperties() override;

    virtual void ReleaseSlateResources(
        bool bReleaseChildren
    ) override;

private:

    // 根据字号和行高比例计算实际行距
    float GetEffectiveTextLineHeight() const;

    TSharedPtr<SNotebookFlowTextEditor> MySlateWidget;

    bool bIsSettingText = false;

    void HandleSlateTextChanged(const FText& InText);
};