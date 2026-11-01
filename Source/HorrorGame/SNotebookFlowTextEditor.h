#pragma once

#include "CoreMinimal.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/Text/SMultiLineEditableText.h"
#include "NotebookFlowTextWidget.h"

// 文字内容变化回调
DECLARE_DELEGATE_OneParam(
    FOnNotebookFlowTextChanged,
    const FText&
);

class HORRORGAME_API SNotebookFlowTextEditor : public SCompoundWidget
{
public:

    // 使用最简单的 Slate 参数结构
    SLATE_BEGIN_ARGS(SNotebookFlowTextEditor)
        {
        }
    SLATE_END_ARGS()

    // 初始化
    void Construct(const FArguments& InArgs);

    // 更新照片避让区域
    void SetPhotoExclusionSquares(
        const TArray<FNotebookPhotoExclusionSquare>& InSquares
    );

    // 更新纸张布局
    void SetPaperLayout(
        FVector2D InPaperSize,
        float InLineSpacing
    );

    // 设置文字
    void SetNotebookText(const FText& InText);

    // 获取文字
    FText GetNotebookText() const;

    // 设置文字变化回调
    void SetOnNotebookTextChanged(
        FOnNotebookFlowTextChanged InDelegate
    );

private:

    FVector2D PaperSize = FVector2D(700.0f, 1000.0f);

    float LineSpacing = 24.0f;

    TArray<FNotebookPhotoExclusionSquare> PhotoExclusionSquares;

    FText NotebookText = FText::GetEmpty();

    FOnNotebookFlowTextChanged OnNotebookTextChanged;

    // 内部文字编辑控件
    TSharedPtr<SMultiLineEditableText> EditableText;

    // 文字变化处理
    void HandleTextChanged(const FText& InText);
};
