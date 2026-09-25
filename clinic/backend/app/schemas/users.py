from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UserListItem(BaseModel):
    user_id: UUID
    username: str
    email: str | None
    phone: str | None
    role: str
    is_active: bool
    created_at: datetime


class UserListResponse(BaseModel):
    items: list[UserListItem]
    page: int
    page_size: int
    total: int
