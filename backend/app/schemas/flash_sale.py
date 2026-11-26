
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class FlashSaleCreate(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    description: str | None = None
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def validate_dates(self):
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("Sale dates must include a timezone")

        if self.ends_at <= self.starts_at:
            raise ValueError("End time must be after start time")

        return self


class FlashSaleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    status: str
    origin: str


class FlashSaleProductCreate(BaseModel):
    product_id: int
    sale_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    allocated_quantity: int = Field(gt=0)


class FlashSaleProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    flash_sale_id: int
    product_id: int
    sale_price: Decimal
    allocated_quantity: int
    sold_quantity: int
