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

    // 横线间距
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Notebook|Layout")
    float LineSpacing = 24.0f;

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
        float InLineSpacing
    );

protected:

    virtual TSharedRef<SWidget> RebuildWidget() override;

    virtual void SynchronizeProperties() override;

    virtual void ReleaseSlateResources(
        bool bReleaseChildren
    ) override;

private:

    TSharedPtr<SNotebookFlowTextEditor> MySlateWidget;

    bool bIsSettingText = false;

    void HandleSlateTextChanged(const FText& InText);
};