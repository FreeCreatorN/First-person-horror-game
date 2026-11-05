
#include "NotebookFlowTextSlateWidget.h"
#include "SNotebookFlowTextEditor.h"

float UNotebookFlowTextSlateWidget::GetEffectiveTextLineHeight() const
{
    // 限制字体大小
    const float SafeFontSize =
        static_cast<float>(FMath::Clamp(FontSize, 6, 72));

    // 限制行高比例
    const float SafeRatio =
        FMath::Clamp(LineHeightRatio, 0.1f, 3.0f);

    // 计算实际文字行高
    return FMath::Max(
        1.0f,
        SafeFontSize * SafeRatio
    );
}

TSharedRef<SWidget> UNotebookFlowTextSlateWidget::RebuildWidget()
{
    // ① 首先创建 Slate 编辑器
    MySlateWidget = SNew(SNotebookFlowTextEditor);

    // ② 同步字体样式
    MySlateWidget->SetNotebookTextStyle(
        FontSize,
        LetterSpacing,
        FontColor
    );

    // ③ 同步纸张尺寸、横线间距和文字行高
    MySlateWidget->SetPaperLayout(
        PaperSize,
        RuleSpacing,
        GetEffectiveTextLineHeight()
    );

    // ④ 同步照片避让区域
    MySlateWidget->SetPhotoExclusionSquares(
        PhotoExclusionSquares
    );

    // ⑤ 同步已有文字
    MySlateWidget->SetNotebookText(
        NotebookText
    );

    // ⑥ 绑定文字变化事件
    MySlateWidget->SetOnNotebookTextChanged(
        FOnNotebookFlowTextChanged::CreateUObject(
            this,
            &UNotebookFlowTextSlateWidget::HandleSlateTextChanged
        )
    );

    // ⑦ 返回创建好的 Slate 控件
    return MySlateWidget.ToSharedRef();
}


void UNotebookFlowTextSlateWidget::SynchronizeProperties()
{
    Super::SynchronizeProperties();

    if (MySlateWidget.IsValid())
    {
        // 更新字体样式
        MySlateWidget->SetNotebookTextStyle(
            FontSize,
            LetterSpacing,
            FontColor
        );

        // 更新纸张尺寸、横线间距和文字行高
        MySlateWidget->SetPaperLayout(
            PaperSize,
            RuleSpacing,
            GetEffectiveTextLineHeight()
        );

        MySlateWidget->SetPhotoExclusionSquares(
            PhotoExclusionSquares
        );

        if (MySlateWidget->GetNotebookText().ToString()
            != NotebookText.ToString())
        {
            MySlateWidget->SetNotebookText(NotebookText);
        }
    }
}

void UNotebookFlowTextSlateWidget::ReleaseSlateResources(
    bool bReleaseChildren)
{
    Super::ReleaseSlateResources(bReleaseChildren);

    MySlateWidget.Reset();
}

void UNotebookFlowTextSlateWidget::SetNotebookText(
    const FText& InText)
{
    NotebookText = InText;

    if (MySlateWidget.IsValid())
    {
        bIsSettingText = true;

        MySlateWidget->SetNotebookText(InText);

        bIsSettingText = false;
    }
}

FText UNotebookFlowTextSlateWidget::GetNotebookText() const
{
    if (MySlateWidget.IsValid())
    {
        return MySlateWidget->GetNotebookText();
    }

    return NotebookText;
}

void UNotebookFlowTextSlateWidget::SetPhotoExclusionSquares(
    const TArray<FNotebookPhotoExclusionSquare>& InSquares)
{
    PhotoExclusionSquares = InSquares;

    UE_LOG(
        LogTemp,
        Warning,
        TEXT("[NotebookFlow] UMG received photo count: %d"),
        InSquares.Num()
    );

    if (MySlateWidget.IsValid())
    {
        UE_LOG(
            LogTemp,
            Warning,
            TEXT("[NotebookFlow] Slate widget is valid")
        );
        MySlateWidget->SetPhotoExclusionSquares(InSquares);
    }
    else
    {
        UE_LOG(
            LogTemp,
            Warning,
            TEXT("[NotebookFlow] Slate widget is NOT valid")
        );
    }
}

void UNotebookFlowTextSlateWidget::SetPaperLayout(
    FVector2D InPaperSize,
    float InRuleSpacing)
{
    // 更新纸张尺寸
    PaperSize = InPaperSize;

    // 更新笔记本横线间距
    RuleSpacing = FMath::Max(
        1.0f,
        InRuleSpacing
    );

    // 计算实际文字行高
    const float TextLineHeight =
        GetEffectiveTextLineHeight();

    // 同步到 Slate 编辑器
    if (MySlateWidget.IsValid())
    {
        MySlateWidget->SetPaperLayout(
            PaperSize,
            RuleSpacing,
            TextLineHeight
        );
    }
}

void UNotebookFlowTextSlateWidget::HandleSlateTextChanged(
    const FText& InText)
{
    if (bIsSettingText)
    {
        return;
    }

    NotebookText = InText;

    OnNotebookTextChanged.Broadcast(InText);
}
