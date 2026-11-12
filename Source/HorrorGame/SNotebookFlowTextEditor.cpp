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

        UE_LOG(
            LogTemp,
            Display,
            TEXT("[NotebookFlow] Layout received Squares=%d | PaperSize=(%.1f, %.1f) | RuleSpacing=%.1f"),
            PhotoExclusionSquares.Num(),
            PaperSize.X,
            PaperSize.Y,
            RuleSpacing
        );

        for (int32 i = 0; i < PhotoExclusionSquares.Num(); ++i)
        {
            const FNotebookPhotoExclusionSquare& Square =
                PhotoExclusionSquares[i];

            UE_LOG(
                LogTemp,
                Display,
                TEXT("[NotebookFlow] Photo=%d | Center=(%.2f, %.2f) | HalfExtent=%.2f"),
                i,
                Square.Center.X,
                Square.Center.Y,
                Square.HalfExtent
            );
        }

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
        // 先让 UE 生成原始文字布局
        FSlateTextLayout::UpdateLayout();

        // 检查布局参数
        if (PaperSize.X <= KINDA_SMALL_NUMBER ||
            PaperSize.Y <= KINDA_SMALL_NUMBER ||
            RuleSpacing <= KINDA_SMALL_NUMBER ||
            TextLineHeight <= KINDA_SMALL_NUMBER)
        {
            return;
        }

        // 保存原始文字布局
        const TArray<FTextLayout::FLineView> SourceViews = LineViews;

        // 清空原来的视图
        LineViews.Reset();

        // 当前物理行编号
        int32 PhysicalRow = 0;

        const TArray<FTextLayout::FLineModel>& Models =
            GetLineModels();

        // 逐条处理原始文字行
        for (const FTextLayout::FLineView& SourceView : SourceViews)
        {
            const TArray<TSharedRef<ILayoutBlock>>& SourceBlocks =
                SourceView.Blocks;

            TArray<int32> BlockCursors;

            bool bHasText = false;

            // 初始化每个文字块的读取位置
            for (const TSharedRef<ILayoutBlock>& Block : SourceBlocks)
            {
                const FTextRange Range = Block->GetTextRange();

                BlockCursors.Add(Range.BeginIndex);

                if (Range.EndIndex > Range.BeginIndex)
                {
                    bHasText = true;
                }
            }

            // 空行保留
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

            const FString& SourceText =
                *Models[SourceView.ModelIndex].Text;

            int32 BlockIndex = 0;

            // 防止连续遇到无法容纳文字的行时无限循环
            int32 ConsecutiveNoProgressRows = 0;

            const int32 MaxNoProgressRows =
                FMath::Max(1, LineSegmentsByRow.Num() + 1);

            // 只要还有未处理的文字，就继续排版
            while (BlockIndex < SourceBlocks.Num())
            {
                // 跳过已经处理完的文字块
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

                // 获取当前物理行的可写区域
                const TArray<FNotebookTextLineSegment> Segments =
                    GetSegmentsForRow(PhysicalRow);

                // 当前整行都被照片遮挡
                if (Segments.IsEmpty())
                {
                    ++PhysicalRow;
                    ++ConsecutiveNoProgressRows;

                    if (ConsecutiveNoProgressRows > MaxNoProgressRows)
                    {
                        UE_LOG(
                            LogTemp,
                            Error,
                            TEXT("[NotebookFlow] Too many blocked rows.")
                        );
                        break;
                    }

                    continue;
                }

                // 每条物理行只创建一个 VisualLine
                FTextLayout::FLineView VisualLine = SourceView;

                VisualLine.Blocks.Reset();

                int32 RowStartIndex = INDEX_NONE;
                int32 RowEndIndex = INDEX_NONE;

                bool bMadeProgress = false;

                // 遍历当前物理行的所有可写区域
                for (const FNotebookTextLineSegment& Segment : Segments)
                {
                    // 无效区域直接跳过
                    if (Segment.EndX <=
                        Segment.StartX + KINDA_SMALL_NUMBER)
                    {
                        continue;
                    }

                    float CurrentX = Segment.StartX;

                    // 当前区域还有可写空间
                    while (CurrentX <
                        Segment.EndX - KINDA_SMALL_NUMBER)
                    {
                        // 跳过已完成的文字块
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

                        const TSharedRef<ILayoutBlock> SourceBlock =
                            SourceBlocks[BlockIndex];

                        const FTextRange SourceRange =
                            SourceBlock->GetTextRange();

                        const int32 CurrentIndex =
                            BlockCursors[BlockIndex];

                        // 防止读取位置超出文字块范围
                        if (CurrentIndex < SourceRange.BeginIndex ||
                            CurrentIndex >= SourceRange.EndIndex)
                        {
                            ++BlockIndex;
                            continue;
                        }

                        const TSharedRef<IRun> Run =
                            SourceBlock->GetRun();

                        const FLayoutBlockTextContext TextContext =
                            SourceBlock->GetTextContext();

                        const TSharedPtr<IRunRenderer> Renderer =
                            SourceBlock->GetRenderer();

                        const float AvailableWidth =
                            Segment.EndX - CurrentX;

                        int32 FitEnd = CurrentIndex;

                        FVector2D FitSize(
                            0.0f,
                            SourceBlock->GetSize().Y
                        );

                        // 测量当前区域能够容纳的文字
                        while (FitEnd < SourceRange.EndIndex)
                        {
                            const int32 NextIndex = GetNextTextIndex(
                                SourceText,
                                FitEnd,
                                SourceRange.EndIndex
                            );

                            if (NextIndex <= FitEnd)
                            {
                                break;
                            }

                            const FVector2D CandidateSize =
                                Run->Measure(
                                    CurrentIndex,
                                    NextIndex,
                                    GetScale(),
                                    TextContext
                                );

                            if (CandidateSize.X >
                                AvailableWidth + KINDA_SMALL_NUMBER)
                            {
                                break;
                            }

                            FitEnd = NextIndex;

                            FitSize = FVector2D(
                                CandidateSize.X,
                                FMath::Max(
                                    CandidateSize.Y,
                                    SourceBlock->GetSize().Y
                                )
                            );
                        }

                        // 当前区域放不下下一个字符
                        // 不换物理行，继续尝试下一个可写区域
                        if (FitEnd == CurrentIndex)
                        {
                            break;
                        }

                        // 创建当前区域对应的文字块
                        TSharedRef<ILayoutBlock> NewBlock =
                            FDefaultLayoutBlock::Create(
                                Run,
                                FTextRange(CurrentIndex, FitEnd),
                                FitSize,
                                TextContext,
                                Renderer
                            );

                        // 设置文字块在当前物理行的位置
                        NewBlock->SetLocationOffset(
                            FVector2D(
                                CurrentX,
                                PhysicalRow * RuleSpacing
                            )
                        );

                        // 添加到当前 VisualLine
                        VisualLine.Blocks.Add(NewBlock);

                        if (RowStartIndex == INDEX_NONE)
                        {
                            RowStartIndex = CurrentIndex;
                        }

                        RowEndIndex = FitEnd;

                        // 更新文字读取位置
                        BlockCursors[BlockIndex] = FitEnd;

                        CurrentX += FitSize.X;

                        bMadeProgress = true;

                        // 当前文字块处理完成
                        if (FitEnd >= SourceRange.EndIndex)
                        {
                            ++BlockIndex;
                        }
                        else
                        {
                            // 当前区域放不下剩余文字
                            // 继续尝试当前行的下一个区域
                            break;
                        }

                        if (BlockIndex >= SourceBlocks.Num())
                        {
                            break;
                        }
                    }

                    if (BlockIndex >= SourceBlocks.Num())
                    {
                        break;
                    }
                }

                // 当前物理行所有区域都无法容纳文字
                if (!bMadeProgress)
                {
                    ++PhysicalRow;
                    ++ConsecutiveNoProgressRows;

                    if (ConsecutiveNoProgressRows > MaxNoProgressRows)
                    {
                        UE_LOG(
                            LogTemp,
                            Error,
                            TEXT("[NotebookFlow] Unable to fit text. Check PaperSize.X and font size.")
                        );
                        break;
                    }

                    continue;
                }

                // 检查文字范围是否合法
                if (RowStartIndex == INDEX_NONE ||
                    RowEndIndex <= RowStartIndex)
                {
                    UE_LOG(
                        LogTemp,
                        Error,
                        TEXT("[NotebookFlow] Invalid text range: %d - %d"),
                        RowStartIndex,
                        RowEndIndex
                    );

                    break;
                }

                // 设置当前物理行的文字范围
                VisualLine.Range = FTextRange(
                    RowStartIndex,
                    RowEndIndex
                );

                // 设置当前物理行的位置
                VisualLine.Offset = FVector2D(
                    0.0f,
                    PhysicalRow * RuleSpacing
                );

                // 设置文字布局高度
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

                // 一条物理行只添加一次
                LineViews.Add(MoveTemp(VisualLine));

                const FTextLayout::FLineView& AddedLine =
                    LineViews.Last();

                UE_LOG(
                    LogTemp,
                    Display,
                    TEXT("[NotebookFlow] Added View: Row=%d | Range=%d-%d | OffsetY=%.2f | Blocks=%d"),
                    PhysicalRow,
                    AddedLine.Range.BeginIndex,
                    AddedLine.Range.EndIndex,
                    AddedLine.Offset.Y,
                    AddedLine.Blocks.Num()
                );

                // 当前行已经成功处理
                ConsecutiveNoProgressRows = 0;

                // 所有区域处理完毕，才进入下一物理行
                ++PhysicalRow;
            }

            // 更新文字高亮和选区
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
                float HalfWidth = Square.HalfWidth;
                float HalfHeight = Square.HalfHeight;

                // 打印照片最终传入 Slate 的位置和避让半尺寸
                if (LineIndex == 0)
                {
                    UE_LOG(
                        LogTemp,
                        Display,
                        TEXT("[NotebookFlow][Check] Center=(%.2f, %.2f) | HalfWidth=%.2f | HalfHeight=%.2f"),
                        Square.Center.X,
                        Square.Center.Y,
                        HalfWidth,
                        HalfHeight
                    );
                }

                // 兼容旧的正方形数据
                if (HalfWidth <= KINDA_SMALL_NUMBER ||
                    HalfHeight <= KINDA_SMALL_NUMBER)
                {
                    HalfWidth = Square.HalfExtent;
                    HalfHeight = Square.HalfExtent;
                }

                if (HalfWidth <= KINDA_SMALL_NUMBER ||
                    HalfHeight <= KINDA_SMALL_NUMBER)
                {
                    continue;
                }

                // 检查横向半宽和纵向半高是否有效
                if (HalfWidth <= KINDA_SMALL_NUMBER ||
                    HalfHeight <= KINDA_SMALL_NUMBER)
                {
                    continue;
                }

                const float PhotoTop = Square.Center.Y - HalfHeight;

                const float PhotoBottom = Square.Center.Y + HalfHeight;

                //判断照片是否与当前横线相交
                if (PhotoBottom <= RowTop ||
                    PhotoTop >= RowBottom)
                {
                    continue;
                }

                FNotebookTextLineSegment Blocked;

                Blocked.StartX = FMath::Clamp(
                    Square.Center.X - HalfWidth,
                    0.0f,
                    PaperSize.X
                );

                Blocked.EndX = FMath::Clamp(
                    Square.Center.X + HalfWidth,
                    0.0f,
                    PaperSize.X
                );

                // 打印当前行实际避让范围
                UE_LOG(
                    LogTemp,
                    Display,
                    TEXT("[NotebookFlow][Check] Row=%d | RowY=%.2f-%.2f | PhotoY=%.2f-%.2f | BlockedX=%.2f-%.2f | Width=%.2f"),
                    LineIndex,
                    RowTop,
                    RowBottom,
                    PhotoTop,
                    PhotoBottom,
                    Blocked.StartX,
                    Blocked.EndX,
                    Blocked.EndX - Blocked.StartX
                );

                if (Blocked.EndX > Blocked.StartX)
                {
                    BlockedRanges.Add(Blocked);
                }
            }

            if (BlockedRanges.Num() > 0)
            {
                UE_LOG(
                    LogTemp,
                    Display,
                    TEXT("[NotebookFlow] Row=%d | RowTop=%.2f | RowBottom=%.2f | BlockedRanges=%d"),
                    LineIndex,
                    RowTop,
                    RowBottom,
                    BlockedRanges.Num()
                );

                for (const FNotebookTextLineSegment& Blocked : BlockedRanges)
                {
                    UE_LOG(
                        LogTemp,
                        Display,
                        TEXT("[NotebookFlow][Editor=%p] PaperWidth=%.2f | BlockedX=%.2f-%.2f | Width=%.2f"),
                        this,
                        PaperSize.X,
                        Blocked.StartX,
                        Blocked.EndX,
                        Blocked.EndX - Blocked.StartX
                    );
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

            if (BlockedRanges.Num() > 0)
            {
                const auto& Segments = LineSegmentsByRow[LineIndex];

                UE_LOG(
                    LogTemp,
                    Display,
                    TEXT("[NotebookFlow] PaperWidth=%.1f | Row=%d | Available=%d"),
                    PaperSize.X,
                    LineIndex,
                    Segments.Num()
                );

                for (const FNotebookTextLineSegment& Segment : Segments)
                {
                    UE_LOG(
                        LogTemp,
                        Display,
                        TEXT("[NotebookFlow] Available X: %.2f - %.2f"),
                        Segment.StartX,
                        Segment.EndX
                    );
                }
            }

            // 输出当前横线生成的可写区间数量
            UE_LOG(
                LogTemp,
                Display,
                TEXT("[NotebookFlow] Row=%d AvailableSegments=%d"),
                LineIndex,
                LineSegmentsByRow[LineIndex].Num()
            );

            // 输出每一个可写区间的实际位置
            for (int32 i = 0;
                i < LineSegmentsByRow[LineIndex].Num();
                ++i)
            {
                const FNotebookTextLineSegment& Segment =
                    LineSegmentsByRow[LineIndex][i];

                UE_LOG(
                    LogTemp,
                    Display,
                    TEXT("[NotebookFlow] Row=%d Segment=%d StartX=%.1f EndX=%.1f Width=%.1f"),
                    LineIndex,
                    i,
                    Segment.StartX,
                    Segment.EndX,
                    Segment.EndX - Segment.StartX
                );
            }
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