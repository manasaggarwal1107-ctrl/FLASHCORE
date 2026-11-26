
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class StoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    store_id: int
    store_type: str | None
    assortment: str | None
    competition_distance: int | None
    competition_open_since_month: int | None
    competition_open_since_year: int | None
    promo2: bool | None
    promo2_since_week: int | None
    promo2_since_year: int | None
    promo_interval: str | None


class DailyStoreSaleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    store_id: int
    sales_date: date
    day_of_week: int
    sales: Decimal
    customers: int
    is_open: bool
    promo: bool
    state_holiday: str
    school_holiday: bool


class SalesSummary(BaseModel):
    total_records: int
    total_sales: Decimal | None
    average_sales: float | None
    highest_sales: Decimal | None
    total_customers: int | None
