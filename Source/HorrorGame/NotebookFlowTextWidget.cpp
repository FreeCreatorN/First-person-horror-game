// Fill out your copyright notice in the Description page of Project Settings.


#include "NotebookFlowTextWidget.h"

void UNotebookFlowTextWidget::SetNotebookText(const FText& InText) 
{
	NotebookText = InText;
}

FText UNotebookFlowTextWidget::GetNotebookText() const
{
	return NotebookText;
}

void UNotebookFlowTextWidget::SetPhotoExclusionSquares(
	const TArray<FNotebookPhotoExclusionSquare>& InSquares)
{
	PhotoExclusionSquares = InSquares;
}

void UNotebookFlowTextWidget::ClearPhotoExclusionSquares()
{
	PhotoExclusionSquares.Empty();
}

TArray<FNotebookTextLineSegment>
UNotebookFlowTextWidget::GetLineAvailableSegments(int32 LineIndex) const
{
	TArray<FNotebookTextLineSegment> AvailableSegments;

	if (LineIndex < 0 ||
		LineSpacing <= 0.00f ||
		PaperSize.X <= 0.0f)
	{
		return AvailableSegments;
	}

	//当前横线对应的整行垂直范围
	const float RowTop = LineIndex * LineSpacing;
	const float RowBottom = RowTop + LineSpacing;

	//收集当前行被照片占据的水平区间
	struct FBlockedRange
	{
		float StartX;
		float EndX;
	};

	TArray<FBlockedRange> BlockedRanges;

	for (const FNotebookPhotoExclusionSquare& Square
		: PhotoExclusionSquares)
	{
		const float Half = FMath::Max(0.0f, Square.HalfExtent);

		if (Half <= KINDA_SMALL_NUMBER)
		{
			continue;
		}

		const float SquareTop = Square.Center.Y - Half;
		const float SquareBottom = Square.Center.Y + Half;

		//照片的正方形与当前行没有垂直交集
		if (SquareBottom <= RowTop ||
			SquareTop >= RowBottom)
		{
			continue;
		}

		const float StartX = FMath::Clamp(
			Square.Center.X - Half, 0.0f, PaperSize.X);

		const float EndX = FMath::Clamp(
			Square.Center.X + Half, 0.0f, PaperSize.X);

		if (EndX > StartX)
		{
			FBlockedRange Range;
			Range.StartX = StartX;
			Range.EndX = EndX;

			BlockedRanges.Add(Range);
		}
	}

	//按照片占据区域的起点排序
	BlockedRanges.Sort(
		[](const FBlockedRange& A, const FBlockedRange& B)
		{
			return A.StartX < B.StartX;
		}
	);

	//合并重叠的照片避让区域
	TArray<FBlockedRange> MergedRanges;

	for (const FBlockedRange& Range : BlockedRanges)
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
				Range.EndX);
		}
	}

	//被占据区域之间的空白就是文字可以书写的区域
	float CursorX = 0.0f;

	for (const FBlockedRange& Range : MergedRanges)
	{
		if (Range.StartX > CursorX + KINDA_SMALL_NUMBER)
		{
			FNotebookTextLineSegment Segment;
			Segment.StartX = CursorX;
			Segment.EndX = Range.StartX;

			AvailableSegments.Add(Segment);
		}

		CursorX = FMath::Max(CursorX, Range.EndX);
	}

	//最后一个照片区域右侧的可写区域
	if (PaperSize.X > CursorX + KINDA_SMALL_NUMBER)
	{
		FNotebookTextLineSegment Segment;
		Segment.StartX = CursorX;
		Segment.EndX = PaperSize.X;

		AvailableSegments.Add(Segment);
	}
	
	return AvailableSegments;
}

FNotebookPhotoExclusionSquare
UNotebookFlowTextWidget::CalculatePhotoExclusionSquare(
	FVector2D PhotoPosition,
	FVector2D PhotoSize,
	float PhotoRotation
)
{
	FNotebookPhotoExclusionSquare Result;

	//照片中心点
	Result.Center = PhotoPosition + PhotoSize * 0.5f;

	//角度旋转为弧度
	const float Radians = FMath::DegreesToRadians(PhotoRotation);

	const float AbsCos = FMath::Abs(FMath::Cos(Radians));
	const float AbsSin = FMath::Abs(FMath::Sin(Radians));

	//照片未旋转时的半宽和半高
	const float HalfWidth = PhotoSize.X * 0.5f;
	const float HalfHeight = PhotoSize.Y * 0.5f;

	//旋转后轴对齐包围盒的半宽盒半高
	const float BoundingHalfWidth = AbsCos * HalfWidth + AbsSin * HalfHeight;
	const float BoundingHalfHeight = AbsSin * HalfWidth + AbsCos * HalfHeight;

	//取较大值，形成能够完整包围照片的正方形
	Result.HalfExtent = FMath::Max(
		BoundingHalfWidth,
		BoundingHalfHeight
	);

	return Result;
}
