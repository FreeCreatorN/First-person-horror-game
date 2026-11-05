#include "SNotebookFlowTextEditor.h"
#include "Styling/CoreStyle.h"
#include "Framework/Text/SlateTextLayout.h"
#include "Framework/Text/SlateTextLayoutFactory.h"
#include "Framework/Text/DefaultLayoutBlock.h"
#include "Framework/Text/ILayoutBlock.h"
#include "Framework/Text/IRun.h"

//自定义笔记本文字布局
class FNotebookFlowTextLayout : public FSlateTextLayout
{
public:

    FNotebookFlowTextLayout(
        SWidget* InOwner,
        const FTextBlockStyle& InStyle
    )
        :FSlateTextLayout(InOwner, InStyle)
    {
        RebuildLineSegments();
    }

    //保存纸张参数
    void SetPaperLayout(
        FVector2D InPaperSize,
        float InRuleSpacing,
        float InTextLineHeight
    )
    {
        // 更新纸张尺寸
        PaperSize = InPaperSize;

        // 更新横线间距
        RuleSpacing = FMath::Max(
            1.0f,
            InRuleSpacing
        );

        // 更新文字排版高度
        TextLineHeight = FMath::Max(
            1.0f,
            InTextLineHeight
        );

        // 重新计算照片避让区域
        RebuildLineSegments();

        // 通知 Slate 重新排版
        DirtyLayout();
    }

    //保存照片避让区域
    void SetPhotoExclusionSquares(
        const TArray<FNotebookPhotoExclusionSquare>& InSquares
    )
    {
        PhotoExclusionSquares = InSquares;

        RebuildLineSegments();

        DirtyLayout();
    }

    //获得指定横线的可写区间
    const TArray<FNotebookTextLineSegment>& GetLineSegments(
        int32 LineIndex
    )const
    {
        static const TArray<FNotebookTextLineSegment> EmptySegments;

        if (!LineSegmentsByRow.IsValidIndex(LineIndex))
        {
            return EmptySegments;
        }

        return LineSegmentsByRow[LineIndex];
    }

    virtual void UpdateLayout() override
    {
        //先让UE生成原始文字布局
        FSlateTextLayout::UpdateLayout();

        // 纸张尺寸无效时，不执行自定义排版
        if (PaperSize.X <= KINDA_SMALL_NUMBER ||
            PaperSize.Y <= KINDA_SMALL_NUMBER ||
            RuleSpacing <= KINDA_SMALL_NUMBER ||
            TextLineHeight <= KINDA_SMALL_NUMBER)
        {
            return;
        }

        //保存原始文字
        const TArray<FTextLayout::FLineView> SourceViews = LineViews;

        //清空原来的视觉行
        LineViews.Reset();

        //当前纸张上的物理横线编号
        int32 PhysicalRow = 0;

        const TArray < FTextLayout::FLineModel >& Models =
            GetLineModels();

        //逐条处理原始文字行
        for (const FTextLayout::FLineView& SourceView : SourceViews)
        {
            const TArray<TSharedRef<ILayoutBlock>>& SourceBlocks = SourceView.Blocks;

            TArray<int32> BlockCursors;

            bool bHasText = false;

            //初始化每个文字块的读取位置
            for (const TSharedRef<ILayoutBlock>& Block : SourceBlocks)
            {
                const FTextRange Range = Block->GetTextRange();

                BlockCursors.Add(Range.BeginIndex);

                if (Range.EndIndex > Range.BeginIndex)
                {
                    bHasText = true;
                }
            }

            //空行也必须保留，方便后续定位光标
            if (!bHasText)
            {
                FTextLayout::FLineView EmptyView = SourceView;

                EmptyView.Offset = FVector2D(
                    0.0f,
                    PhysicalRow * RuleSpacing
                );

                EmptyView.Size = FVector2D(
                    PaperSize.X,
                    TextLineHeight
                );

                EmptyView.TextHeight = TextLineHeight;
                EmptyView.JustificationWidth = PaperSize.X;

                LineViews.Add(MoveTemp(EmptyView));

                ++PhysicalRow;
                continue;
            }

            if (!Models.IsValidIndex(SourceView.ModelIndex))
            {
                continue;
            }

            const FString& SourceText = *Models[SourceView.ModelIndex].Text;

            int32 BlockIndex = 0;

            //当前逻辑文字行可能占据多个物理横线
            while (BlockIndex < SourceBlocks.Num())
            {
                //跳过已近处理完成的文字块
                while (BlockIndex < SourceBlocks.Num() &&
                    BlockCursors[BlockIndex] >=
                    SourceBlocks[BlockIndex]->GetTextRange().EndIndex)
                {
                    ++BlockIndex;
                }

                if (BlockIndex >= SourceBlocks.Num())
                {
                    break;
                }

                //获取当前横线的可写区间
                const TArray<FNotebookTextLineSegment> Segments =
                    GetSegmentsForRow(PhysicalRow);

                // 当前横线没有可写区域，直接尝试下一行
                if (Segments.IsEmpty())
                {
                    ++PhysicalRow;
                    continue;
                }

                FTextLayout::FLineView VisualLine = SourceView;

                VisualLine.Blocks.Reset();

                int32 RowStartIndex = INDEX_NONE;
                int32 RowEndIndex = INDEX_NONE;

                bool bMadeProgress = false;

                //依次填充当前横线上的所有可写区间
                for (const FNotebookTextLineSegment& Segment : Segments)
                {
                    float CurrentX = Segment.StartX;

                    while (CurrentX < Segment.EndX - KINDA_SMALL_NUMBER)
                    {
                        while (BlockIndex < SourceBlocks.Num() &&
                            BlockCursors[BlockIndex] >=
                            SourceBlocks[BlockIndex]->GetTextRange().EndIndex)
                        {   ++BlockIndex;   }

                        if (BlockIndex >= SourceBlocks.Num())
                            break;

                        const TSharedRef<ILayoutBlock> SourceBlock = SourceBlocks[BlockIndex];

                        const FTextRange SourceRange = SourceBlock->GetTextRange();

                        const int32 CurrentIndex = BlockCursors[BlockIndex];

                        const TSharedRef<IRun> Run = SourceBlock->GetRun();

                        const FLayoutBlockTextContext TextContext = SourceBlock->GetTextContext();

                        const TSharedPtr<IRunRenderer> Renderer = SourceBlock->GetRenderer();

                        const float AvailableWidth = Segment.EndX - CurrentX;

                        int32 FitEnd = CurrentIndex;

                        FVector2D FitSize(
                            0.0f,
                            SourceBlock->GetSize().Y
                        );

                        //使用真实文字宽度寻找能够放入的文字范围
                        while (FitEnd < SourceRange.EndIndex)
                        {
                            const int32 NextIndex = GetNextTextIndex(
                                SourceText,
                                FitEnd,
                                SourceRange.EndIndex
                            );

                            const FVector2D CandidateSize =
                                Run->Measure(
                                    CurrentIndex,
                                    NextIndex,
                                    GetScale(),
                                    TextContext
                                );

                            if (CandidateSize.X >
                                AvailableWidth + KINDA_SMALL_NUMBER)
                                break;

                            FitEnd = NextIndex;

                            FitSize = FVector2D(
                                CandidateSize.X,
                                FMath::Max(
                                    CandidateSize.Y,
                                    SourceBlock->GetSize().Y
                                )
                            );
                        }

                        //当前区间放不下下一个字符，尝试下一个区间
                        if (FitEnd == CurrentIndex) break;

                        //创建当前区间对应的文字块
                        TSharedRef<ILayoutBlock> NewBlock =
                            FDefaultLayoutBlock::Create(
                                Run,
                                FTextRange(CurrentIndex, FitEnd),
                                FitSize,
                                TextContext,
                                Renderer
                            );

                        //设置文字块在纸张上的水平位置
                        NewBlock->SetLocationOffset(
                            FVector2D(
                                CurrentX,
                                PhysicalRow * RuleSpacing
                            )
                        );

                        VisualLine.Blocks.Add(NewBlock);

                        if (RowStartIndex == INDEX_NONE) RowStartIndex = CurrentIndex;;

                        RowEndIndex = FitEnd;

                        //更新当前文字块读取位置
                        BlockCursors[BlockIndex] = FitEnd;

                        CurrentX += FitSize.X;

                        bMadeProgress = true;

                        //当前文字块已近全部处理完
                        if (FitEnd >= SourceRange.EndIndex) ++BlockIndex;
                        else break;

                        if (BlockIndex >= SourceBlocks.Num()) break;
                    }

                    // 当前横线没有容纳任何文字，跳到下一横线
                    if (!bMadeProgress)
                    {
                        ++PhysicalRow;
                        continue;
                    }

                    //设置当前视觉行的文字范围
                    VisualLine.Range = FTextRange(
                        RowStartIndex,
                        RowEndIndex
                    );

                    //设置当前视觉行的位置
                    VisualLine.Offset = FVector2D(
                        0.0f,
                        PhysicalRow * RuleSpacing
                    );

                    VisualLine.Size = FVector2D(
                        PaperSize.X,
                        FMath::Max(
                            TextLineHeight,
                            SourceView.TextHeight
                        )
                    );

                    VisualLine.TextHeight = FMath::Max(
                        TextLineHeight,
                        SourceView.TextHeight
                    );


                    VisualLine.JustificationWidth = PaperSize.X;

                    LineViews.Add(MoveTemp(VisualLine));

                    const FTextLayout::FLineView& AddedLine = LineViews.Last();

                    UE_LOG(
                        LogTemp,
                        Warning,
                        TEXT("[NotebookFlow] Added View: Row=%d | Range=%d-%d | OffsetY=%.2f | Blocks=%d"),
                        PhysicalRow,
                        AddedLine.Range.BeginIndex,
                        AddedLine.Range.EndIndex,
                        AddedLine.Offset.Y,
                        AddedLine.Blocks.Num()
                    );

                    ++PhysicalRow;
                }
            }

            //根据新的视觉行重新计算文字高亮与选择区域
            UpdateHighlights();
        }
    }

private:

    //纸张尺寸
    FVector2D PaperSize = FVector2D(700.0f, 1000.0f);

    // 笔记本横线间距
    float RuleSpacing = 30.0f;

    // 文字实际排版高度
    float TextLineHeight = 19.6f;

    //照片避让区域
    TArray<FNotebookPhotoExclusionSquare> PhotoExclusionSquares;

    //每条横线对应的可写区间
    TArray<TArray<FNotebookTextLineSegment>> LineSegmentsByRow;
 
    //重新计算所有横线的可写区间
    void RebuildLineSegments()
    {
        LineSegmentsByRow.Reset();

        if (PaperSize.X <= 0.0f ||
            PaperSize.Y <= 0.0f ||
            RuleSpacing <= 0.0f)
        {
            return;
        }

        const int32 RowCount = FMath::CeilToInt(
            PaperSize.Y / RuleSpacing
        );

        LineSegmentsByRow.SetNum(RowCount);

        //逐条计算横线
        for (int32 LineIndex = 0;
            LineIndex < RowCount;
            ++LineIndex)
        {
            const float RowTop = LineIndex * RuleSpacing;

            const float RowBottom = RowTop + RuleSpacing;

            //收集照片占据的水平区间
            TArray<FNotebookTextLineSegment> BlockedRanges;

            for (const FNotebookPhotoExclusionSquare& Square : PhotoExclusionSquares)
            {
                const float Half = FMath::Max(
                    0.0f,
                    Square.HalfExtent
                );

                if (Half <= KINDA_SMALL_NUMBER)
                {
                    continue;
                }

                const float SquareTop = Square.Center.Y - Half;

                const float SquareBottom = Square.Center.Y + Half;

                //判断照片是否与当前横线相交
                if (SquareBottom <= RowTop ||
                    SquareTop >= RowBottom)
                {
                    continue;
                }

                FNotebookTextLineSegment Blocked;

                Blocked.StartX = FMath::Clamp(
                    Square.Center.X - Half,
                    0.0f,
                    PaperSize.X
                );

                Blocked.EndX = FMath::Clamp(
                    Square.Center.X + Half,
                    0.0f,
                    PaperSize.X
                );

                if (Blocked.EndX > Blocked.StartX)
                {
                    BlockedRanges.Add(Blocked);
                }
            }

            //按照片区域的起点排序
            BlockedRanges.Sort(
                [](const FNotebookTextLineSegment& A,
                    const FNotebookTextLineSegment& B)
                {
                    return A.StartX < B.StartX;
                }
            );


            //合并重叠区域
            TArray<FNotebookTextLineSegment> MergedRanges;

            for (const FNotebookTextLineSegment& Range
                : BlockedRanges)
            {
                if (MergedRanges.IsEmpty() ||
                    Range.StartX > MergedRanges.Last().EndX)
                {
                    MergedRanges.Add(Range);
                }
                else 
                {
                    MergedRanges.Last().EndX = FMath::Max(
                        MergedRanges.Last().EndX,
                        Range.EndX
                    );
                }
            }

            //计算照片之间的可写区间
            float CursorX = 0.0f;

            for (const FNotebookTextLineSegment& Range : MergedRanges)
            {
                if (Range.StartX > CursorX + KINDA_SMALL_NUMBER)
                {
                    FNotebookTextLineSegment Available;

                    Available.StartX = CursorX;
                    Available.EndX = Range.StartX;

                    LineSegmentsByRow[LineIndex].Add(Available);
                }

                CursorX = FMath::Max(CursorX, Range.EndX);
            }
            
            // 注意：这一部分必须放在上面的 for 循环外面
            // 即使没有照片，也必须生成整行可写区域
            if (PaperSize.X > CursorX + KINDA_SMALL_NUMBER)
            {
                FNotebookTextLineSegment Available;

                Available.StartX = CursorX;
                Available.EndX = PaperSize.X;

                LineSegmentsByRow[LineIndex].Add(Available);
            }

            /*
            for (const FNotebookTextLineSegment& Range
                : MergedRanges)
            {
                if (Range.StartX >
                    CursorX + KINDA_SMALL_NUMBER)
                {
                    FNotebookTextLineSegment Available;

                    Available.StartX = CursorX;
                    Available.EndX = Range.StartX;

                    LineSegmentsByRow[LineIndex].Add(
                        Available
                    );
                }

                CursorX = FMath::Max(
                    CursorX,
                    Range.EndX
                );

                //最后一个照片区域右侧
                if (PaperSize.X >
                    CursorX + KINDA_SMALL_NUMBER)
                {
                    FNotebookTextLineSegment Available;

                    Available.StartX = CursorX;
                    Available.EndX = PaperSize.X;

                    LineSegmentsByRow[LineIndex].Add(
                        Available
                    );
                }
            }
            */
        }
    }

    TArray<FNotebookTextLineSegment> GetSegmentsForRow(
        int32 RowIndex
    )const
    {
        if (LineSegmentsByRow.IsValidIndex(RowIndex))
            return LineSegmentsByRow[RowIndex];

        //超出纸张高度后，暂时允许使用完整宽度
        TArray<FNotebookTextLineSegment> Result;

        if (PaperSize.X > 0.0f)
        {
            FNotebookTextLineSegment FullSegment;

            FullSegment.StartX = 0.0f;
            FullSegment.EndX = PaperSize.X;

            Result.Add(FullSegment);
        }

        return Result;
    }

    //获取下一个Unicode 字符的结束位置
    int32 GetNextTextIndex(
        const FString& Text,
        int32 CurrentIndex,
        int32 EndIndex
    )const
    {
        int32 NextIndex = CurrentIndex + 1;

        //避免拆开UTF-16代理对
        if (CurrentIndex >= 0 &&
            CurrentIndex + 1 < EndIndex &&
            CurrentIndex + 1 < Text.Len())
        {
            const uint32 First = static_cast<uint32>(Text[CurrentIndex]);

            const uint32 Second = static_cast<uint32>(Text[CurrentIndex + 1]);

            if (First >= 0xD800 && First <= 0xDBFF &&
                Second >= 0xDC00 && Second <= 0xDFFF)
                NextIndex = CurrentIndex + 2;
        }

        return FMath::Min(NextIndex, EndIndex);
    }
};

void SNotebookFlowTextEditor::Construct(const FArguments& InArgs)
{
    NotebookTextStyle =
        FCoreStyle::Get().GetWidgetStyle<FTextBlockStyle>("NormalText");

    SetNotebookTextStyle(
        14,
        0,
        FColor(38, 38, 38, 255)
    );

    ChildSlot
        [
            SAssignNew(EditableText, SMultiLineEditableText)

                // 应用自定义文字样式
                .TextStyle(&NotebookTextStyle)

                .CreateSlateTextLayout(
                    FCreateSlateTextLayout::CreateSP(
                        this,
                        &SNotebookFlowTextEditor::CreateNotebookTextLayout
                    )
                )

                .Text(NotebookText)

                .AutoWrapText(false)

                .OnTextChanged(
                    this,
                    &SNotebookFlowTextEditor::HandleTextChanged
                )
        ];
}

void SNotebookFlowTextEditor::SetNotebookTextStyle(
    int32 InFontSize,
    int32 InLetterSpacing,
    const FColor& InFontColor
)
{
    // 设置字体大小
    NotebookTextStyle.Font.Size =
        FMath::Clamp(InFontSize, 6, 72);

    // 设置字间距
    NotebookTextStyle.Font.LetterSpacing =
        InLetterSpacing;

    // 设置字体颜色
    NotebookTextStyle.ColorAndOpacity =
        FSlateColor(
            FLinearColor::FromSRGBColor(InFontColor)
        );

    // 将新样式同步到实际 Slate 编辑器
    if (EditableText.IsValid())
    {
        EditableText->SetTextStyle(&NotebookTextStyle);
        EditableText->Refresh();
    }
}

void SNotebookFlowTextEditor::SetPhotoExclusionSquares(
    const TArray<FNotebookPhotoExclusionSquare>& InSquares)
{
    PhotoExclusionSquares = InSquares;

    UE_LOG(LogTemp, Display,
        TEXT("[C] Slate Editor received photo exclusion data. Count: %d"),
        InSquares.Num());

    if (NotebookTextLayout.IsValid())
    {
        NotebookTextLayout->SetPhotoExclusionSquares(
            PhotoExclusionSquares
        );
    }

    if (EditableText.IsValid())
    {
        EditableText->Refresh();
    }
}

void SNotebookFlowTextEditor::SetPaperLayout(
    FVector2D InPaperSize,
    float InRuleSpacing,
    float InTextLineHeight)
{
    // 更新纸张尺寸
    PaperSize = InPaperSize;

    // 更新横线间距
    RuleSpacing = FMath::Max(
        1.0f,
        InRuleSpacing
    );

    // 更新文字排版高度
    TextLineHeight = FMath::Max(
        1.0f,
        InTextLineHeight
    );

    // 同步到自定义文字布局
    if (NotebookTextLayout.IsValid())
    {
        NotebookTextLayout->SetPaperLayout(
            PaperSize,
            RuleSpacing,
            TextLineHeight
        );
    }

    // 刷新编辑器
    if (EditableText.IsValid())
    {
        EditableText->Refresh();
    }
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
    const bool bValid = EditableText.IsValid();

    const FText Result = bValid
        ? EditableText->GetText()
        : NotebookText;

    FString DebugText = Result.ToString();

    UE_LOG(LogTemp, Display,
        TEXT("[FlowText] GetNotebookText: Valid=%d, Len=%d, Text=%s"),
        bValid ? 1 : 0,
        DebugText.Len(),
        *DebugText);

    return Result;
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

    FString DebugText = InText.ToString();

    UE_LOG(LogTemp, Display,
        TEXT("[FlowText] HandleTextChanged: Len=%d, Text=%s"),
        DebugText.Len(),
        *DebugText);

    OnNotebookTextChanged.ExecuteIfBound(InText);
}

TSharedRef<FSlateTextLayout>
SNotebookFlowTextEditor::CreateNotebookTextLayout(
    SWidget* InOwner,
    const FTextBlockStyle& InStyle)
{
    NotebookTextLayout =
        MakeShared<FNotebookFlowTextLayout>(
            InOwner,
            InStyle
        );

    NotebookTextLayout->SetPaperLayout(
        PaperSize,
        RuleSpacing,
        TextLineHeight
    );

    NotebookTextLayout->SetPhotoExclusionSquares(
        PhotoExclusionSquares
    );

    return NotebookTextLayout.ToSharedRef();
}