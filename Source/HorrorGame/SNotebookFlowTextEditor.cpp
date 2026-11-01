#include "SNotebookFlowTextEditor.h"

void SNotebookFlowTextEditor::Construct(const FArguments& InArgs)
{
    ChildSlot
        [
            SAssignNew(EditableText, SMultiLineEditableText)

                .Text(NotebookText)

                .AutoWrapText(false)

                .OnTextChanged(
                    this,
                    &SNotebookFlowTextEditor::HandleTextChanged
                )
        ];
}

void SNotebookFlowTextEditor::SetPhotoExclusionSquares(
    const TArray<FNotebookPhotoExclusionSquare>& InSquares)
{
    PhotoExclusionSquares = InSquares;
}

void SNotebookFlowTextEditor::SetPaperLayout(
    FVector2D InPaperSize,
    float InLineSpacing)
{
    PaperSize = InPaperSize;

    LineSpacing = FMath::Max(1.0f, InLineSpacing);
}

void SNotebookFlowTextEditor::SetNotebookText(
    const FText& InText)
{
    NotebookText = InText;

    if (EditableText.IsValid())
    {
        EditableText->SetText(NotebookText);
    }
}

FText SNotebookFlowTextEditor::GetNotebookText() const
{
    if (EditableText.IsValid())
    {
        return EditableText->GetText();
    }

    return NotebookText;
}

void SNotebookFlowTextEditor::SetOnNotebookTextChanged(
    FOnNotebookFlowTextChanged InDelegate)
{
    OnNotebookTextChanged = MoveTemp(InDelegate);
}

void SNotebookFlowTextEditor::HandleTextChanged(
    const FText& InText)
{
    NotebookText = InText;

    OnNotebookTextChanged.ExecuteIfBound(InText);
}
