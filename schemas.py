from pydantic import BaseModel, HttpUrl, constr, conlist
from typing import Literal

class Image(BaseModel):
    url: HttpUrl

class LotIn(BaseModel):
    webhook: HttpUrl
    lot_id: constr(strip_whitespace=True, min_length=1)
    additional_info: str | None = None
    images: conlist(Image, min_length=1, max_length=20)

class RequestIn(BaseModel):
    version: Literal["1.0.0"]
    languages: conlist(str, min_length=1)
    lots: conlist(LotIn, min_length=1)
    signature: str


class DamageDesc(BaseModel):
    language: str
    damages: str


class LotOut(BaseModel):
    lot_id: str
    descriptions: list[DamageDesc]


class ResponseOut(BaseModel):
    signature: str
    version: str = "1.0.0"
    lots: list[LotOut]


class SyncResponseOut(BaseModel):
    signature: str | None = None
    version: str = "1.0.0"
    lots: list[LotOut]
