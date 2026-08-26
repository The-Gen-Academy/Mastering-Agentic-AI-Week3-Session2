"""Pydantic models for the course platform."""

from typing import Literal, Optional

from pydantic import BaseModel

ItemType = Literal[
    "live_session",
    "office_hours",
    "guest_lecture",
    "topic_group",
    "project",
    "reading",
]

ResourceKind = Literal["link", "text"]


class Resource(BaseModel):
    id: str
    label: str
    kind: ResourceKind
    # A link resource with url=None is a visible placeholder ("coming soon").
    url: Optional[str] = None
    text: Optional[str] = None


class Item(BaseModel):
    id: str
    title: str
    type: ItemType
    date: Optional[str] = None  # ISO date; topic groups / readings are undated
    start_time: Optional[str] = None  # "HH:MM"
    end_time: Optional[str] = None
    timezone: str = "GMT+5:30"
    optional: bool = False
    completed: bool = False
    resources: list[Resource] = []


class Week(BaseModel):
    number: int
    title: str
    start_date: str
    end_date: str
    items: list[Item] = []


class Course(BaseModel):
    title: str
    subtitle: str = ""
    weeks: list[Week] = []


# ---- request bodies ----


class ItemUpdate(BaseModel):
    """Partial update for an item. Only provided fields are applied."""

    title: Optional[str] = None
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    timezone: Optional[str] = None
    optional: Optional[bool] = None
    completed: Optional[bool] = None


class ResourceCreate(BaseModel):
    label: str
    kind: ResourceKind = "link"
    url: Optional[str] = None
    text: Optional[str] = None


class ResourceUpdate(BaseModel):
    """Partial update for a resource. Only provided fields are applied."""

    label: Optional[str] = None
    url: Optional[str] = None
    text: Optional[str] = None
