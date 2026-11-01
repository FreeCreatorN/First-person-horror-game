
#include "NotebookFlowTextSlateWidget.h"
#include "SNotebookFlowTextEditor.h"

TSharedRef<SWidget> UNotebookFlowTextSlateWidget::RebuildWidget()
{
    MySlateWidget = SNew(SNotebookFlowTextEditor);

    MySlateWidget->SetPaperLayout(
        PaperSize,
        LineSpacing
    );

    MySlateWidget->SetPhotoExclusionSquares(
        PhotoExclusionSquares
    );

    MySlateWidget->SetNotebookText(
        NotebookText
    );

    MySlateWidget->SetOnNotebookTextChanged(
        FOnNotebookFlowTextChanged::CreateUObject(
            this,
            &UNotebookFlowTextSlateWidget::HandleSlateTextChanged
        )
    );

    return MySlateWidget.ToSharedRef();
}

void UNotebookFlowTextSlateWidget::SynchronizeProperties()
{
    Super::SynchronizeProperties();

    if (MySlateWidget.IsValid())
    {
        MySlateWidget->SetPaperLayout(
            PaperSize,
            LineSpacing
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

    if (MySlateWidget.IsValid())
    {
        MySlateWidget->SetPhotoExclusionSquares(InSquares);
    }
}

void UNotebookFlowTextSlateWidget::SetPaperLayout(
    FVector2D InPaperSize,
    float InLineSpacing)
{
    PaperSize = InPaperSize;

    LineSpacing = FMath::Max(1.0f, InLineSpacing);

    if (MySlateWidget.IsValid())
    {
        MySlateWidget->SetPaperLayout(
            PaperSize,
            LineSpacing
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
