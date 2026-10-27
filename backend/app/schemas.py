from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Login(StrictModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)

class ItemInput(StrictModel):
    menu_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=20)
    option_ids: list[int] = Field(default_factory=list, max_length=10)
    @field_validator('option_ids')
    @classmethod
    def unique_options(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('옵션을 중복 선택할 수 없습니다.')
        return sorted(value)

class OrderInput(StrictModel):
    items: list[ItemInput] = Field(min_length=1, max_length=30)
    note: str = Field(default='', max_length=300)

class StatusInput(StrictModel):
    status: Literal['cooking', 'completed']

class OptionInput(StrictModel):
    name: str = Field(min_length=1, max_length=60)
    price: int = Field(ge=0, le=100000)

class MenuInput(StrictModel):
    category_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=1000)
    price: int = Field(ge=0, le=1000000)
    image_url: str = Field(default='/images/burger.jpg', max_length=1000)
    sold_out: bool = False
    badge: str = Field(default='', max_length=30)
    options: list[OptionInput] = Field(default_factory=list, max_length=10)
    @field_validator('image_url')
    @classmethod
    def safe_image(cls, v):
        if not (v.startswith('/images/') or v.startswith('https://')):
            raise ValueError('이미지는 /images/ 경로 또는 HTTPS URL이어야 합니다.')
        return v

class AvailabilityInput(StrictModel):
    sold_out: bool

class AnalysisInput(StrictModel):
    question: str = Field(min_length=1, max_length=500)
    days: Literal[1, 7] = 1
