from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reviews import Review as ReviewModel
from app.models.products import Product as ProductModel
from app.models.users import User as UserModel
from app.schemas import Review as ReviewSchema, ReviewCreate
from app.db_depends import get_async_db
from app.auth import get_current_buyer, get_current_admin

router = APIRouter(
    prefix="/reviews",
    tags=["reviews"],
)


async def update_product_rating(db: AsyncSession, product_id: int):
    """
    Пересчитывает средний рейтинг товара на основе всех активных отзывов.
    """
    result = await db.execute(
        select(func.avg(ReviewModel.grade)).where(
            ReviewModel.product_id == product_id,
            ReviewModel.is_active == True
        )
    )
    avg_rating = result.scalar() or 0.0
    
    product = await db.get(ProductModel, product_id)
    if product:
        product.rating = round(float(avg_rating), 2)
        await db.commit()
        await db.refresh(product)


@router.get("/", response_model=list[ReviewSchema])
async def get_all_reviews(db: AsyncSession = Depends(get_async_db)):
    """
    Возвращает список всех активных отзывов о товарах.
    Доступ: Разрешён всем (аутентификация не требуется).
    """
    result = await db.scalars(
        select(ReviewModel).where(ReviewModel.is_active == True)
    )
    return result.all()


@router.post("/", response_model=ReviewSchema, status_code=status.HTTP_201_CREATED)
async def create_review(
    review: ReviewCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_buyer)
):
    """
    Создаёт новый отзыв для указанного товара.
    После добавления отзыва пересчитывает средний рейтинг товара.
    Доступ: Только аутентифицированные пользователи с ролью "buyer".
    """
    # Проверяем, существует ли активный товар
    product_result = await db.scalars(
        select(ProductModel).where(
            ProductModel.id == review.product_id,
            ProductModel.is_active == True
        )
    )
    product = product_result.first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or inactive"
        )
    
    # Проверяем, не оставлял ли уже пользователь отзыв на этот товар
    existing_review_result = await db.scalars(
        select(ReviewModel).where(
            ReviewModel.user_id == current_user.id,
            ReviewModel.product_id == review.product_id,
            ReviewModel.is_active == True
        )
    )
    existing_review = existing_review_result.first()
    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already left a review for this product"
        )
    
    # Создаём отзыв
    db_review = ReviewModel(
        user_id=current_user.id,
        product_id=review.product_id,
        comment=review.comment,
        grade=review.grade,
        is_active=True
    )
    db.add(db_review)
    await db.commit()
    await db.refresh(db_review)
    
    # Пересчитываем рейтинг товара
    await update_product_rating(db, review.product_id)
    
    return db_review


@router.delete("/{review_id}", status_code=status.HTTP_200_OK)
async def delete_review(
    review_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_admin)
):
    """
    Выполняет мягкое удаление отзыва по review_id, устанавливая is_active = False.
    После удаления пересчитывает рейтинг товара.
    Доступ: Только пользователи с ролью "admin".
    
    **Примечание:** Пользователи без роли "admin" получат ошибку 403 Forbidden при попытке доступа.
    """
    review_result = await db.scalars(
        select(ReviewModel).where(
            ReviewModel.id == review_id,
            ReviewModel.is_active == True
        )
    )
    review = review_result.first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found or already inactive"
        )
    
    # Сохраняем product_id перед удалением
    product_id = review.product_id
    
    # Мягкое удаление отзыва
    await db.execute(
        update(ReviewModel).where(ReviewModel.id == review_id).values(is_active=False)
    )
    await db.commit()
    
    # Пересчитываем рейтинг товара
    await update_product_rating(db, product_id)
    
    return {"message": "Review deleted"}

