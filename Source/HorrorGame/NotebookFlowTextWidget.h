// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "NotebookFlowTextWidget.generated.h"


//照片的正方形避让区域
USTRUCT(BlueprintType)
struct FNotebookPhotoExclusionSquare
{
	GENERATED_BODY()

	//正方形中心，使用纸张局部坐标
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Notebook|Layout")
	FVector2D Center = FVector2D::ZeroVector;

	//正方形半边长
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Notebook|Layout")
	float HalfExtent = 0.0f;
};

//一段可以书写的水平区域
USTRUCT(BlueprintType)
struct  FNotebookTextLineSegment
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Notebook|Layout")
	float StartX = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Notebook|Layout")
	float EndX = 0.0f;
};

UCLASS()
class HORRORGAME_API UNotebookFlowTextWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	//纸张尺寸，单位为UMG 局部坐标
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Notebook|Layout")
	FVector2D PaperSize = FVector2D(700.0f, 1000.0f);

	//横线之间的垂直距离
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Notebook|Layout")
	float LineSpacing = 24.0f;

	//当前页面所有照片的避让区域
	UPROPERTY(BlueprintReadOnly, Category = "Notebook|Layout")
	TArray<FNotebookPhotoExclusionSquare> PhotoExclusionSquares;

	//当前文字内容
	UPROPERTY(BlueprintReadWrite, Category = "Notebook|Text")
	FText NotebookText;

	//设置文字内容
	UFUNCTION(BlueprintCallable, Category = "Notebook|Text")
	void SetNotebookText(const FText& InText);

	//获取文字内容
	UFUNCTION(BlueprintCallable, Category = "Notebook|Text")
	FText GetNotebookText() const;

	//更新照片避让区域
	UFUNCTION(BlueprintCallable, Category = "Notebook|Layout")
	void SetPhotoExclusionSquares(
		const TArray<FNotebookPhotoExclusionSquare>& InSquares
	);

	//根据照片的位置、尺寸和旋转角度计算正方形避让区域
	UFUNCTION(BlueprintPure, Category = "Notebook|Layout")
	static FNotebookPhotoExclusionSquare CalculatePhotoExclusionSquare(
		FVector2D PhotoPosition,
		FVector2D PhotoSize,
		float PhotoRotation
	);

	//清空照片避让区域
	UFUNCTION(BlueprintCallable, Category = "Notebook|Layout")
	void ClearPhotoExclusionSquares();

	//计算指定横线可供文字使用的水平区段
	UFUNCTION(BlueprintPure, Category = "Notebook|Layout")
	TArray<FNotebookTextLineSegment> GetLineAvailableSegments(
		int32 LineIndex
	) const;
};
/**
 * 
 */

