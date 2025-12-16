from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Computed, ForeignKey, Index, String, Boolean, Integer, Numeric, Float, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sqlalchemy.dialects.postgresql import TSVECTOR

from app.database import Base

if TYPE_CHECKING:
    from .categories import Category
    from .reviews import Review

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    rating: Mapped[float] = mapped_column(Float, default=0.0, server_default=text('0'))
    
    
    tsv: Mapped[TSVECTOR] = mapped_column(
        TSVECTOR,
        Computed(
            """
            setweight(to_tsvector('english', coalesce(name, '')), 'A')
            || setweight(to_tsvector('russian', coalesce(name, '')), 'A')
            || setweight(to_tsvector('english', coalesce(description, '')), 'B')
            || setweight(to_tsvector('russian', coalesce(description, '')), 'B')
            """,
            persisted=True,
        ),
        nullable=False,
    )

    category: Mapped["Category"] = relationship("Category", back_populates="products")
    seller = relationship("User", back_populates="products")
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="product")

    

    __table_args__ = (
        Index("ix_products_tsv_gin", "tsv", postgresql_using="gin"),
    )
