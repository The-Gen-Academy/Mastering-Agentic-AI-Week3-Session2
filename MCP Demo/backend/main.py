"""Course platform API.

Deliberately plain, resource-oriented CRUD. No auth — every endpoint is
open. The interesting design lives in the MCP server, which consumes this
API; the React frontend only uses the GET endpoints.

Run: ./dev backend (from the project root), or ../dev backend (from backend/).
"""

import secrets
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import (
    Course,
    Item,
    ItemUpdate,
    Resource,
    ResourceCreate,
    ResourceUpdate,
    Week,
)
from storage import load_course, save_course

app = FastAPI(
    title="Course Platform API",
    description="Mock course platform backing the MCP tutorial. File-backed, no auth.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _find_item(course: Course, item_id: str) -> tuple[Week, Item]:
    for week in course.weeks:
        for item in week.items:
            if item.id == item_id:
                return week, item
    raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")


def _find_resource(item: Item, resource_id: str) -> Resource:
    for res in item.resources:
        if res.id == resource_id:
            return res
    raise HTTPException(
        status_code=404,
        detail=f"Resource '{resource_id}' not found on item '{item.id}'",
    )


# ---- reads ----


@app.get("/curriculum", response_model=Course)
def get_curriculum():
    """Full course tree: weeks, items, resources."""
    return load_course()


@app.get("/weeks/{number}", response_model=Week)
def get_week(number: int):
    course = load_course()
    for week in course.weeks:
        if week.number == number:
            return week
    raise HTTPException(status_code=404, detail=f"Week {number} not found")


@app.get("/items", response_model=list[Item])
def list_items(
    week: Optional[int] = None,
    type: Optional[str] = None,
    date: Optional[str] = None,
):
    """Flat item listing with optional filters."""
    course = load_course()
    results: list[Item] = []
    for w in course.weeks:
        if week is not None and w.number != week:
            continue
        for item in w.items:
            if type is not None and item.type != type:
                continue
            if date is not None and item.date != date:
                continue
            results.append(item)
    return results


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: str):
    course = load_course()
    _, item = _find_item(course, item_id)
    return item


# ---- writes ----


@app.patch("/items/{item_id}", response_model=Item)
def update_item(item_id: str, update: ItemUpdate):
    course = load_course()
    _, item = _find_item(course, item_id)
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    save_course(course)
    return item


@app.post("/items/{item_id}/resources", response_model=Resource, status_code=201)
def add_resource(item_id: str, body: ResourceCreate):
    course = load_course()
    _, item = _find_item(course, item_id)
    resource = Resource(
        id=f"res_{secrets.token_hex(4)}",
        label=body.label,
        kind=body.kind,
        url=body.url,
        text=body.text,
    )
    item.resources.append(resource)
    save_course(course)
    return resource


@app.patch("/items/{item_id}/resources/{resource_id}", response_model=Resource)
def update_resource(item_id: str, resource_id: str, update: ResourceUpdate):
    course = load_course()
    _, item = _find_item(course, item_id)
    resource = _find_resource(item, resource_id)
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(resource, field, value)
    save_course(course)
    return resource


@app.delete("/items/{item_id}/resources/{resource_id}", status_code=204)
def delete_resource(item_id: str, resource_id: str):
    course = load_course()
    _, item = _find_item(course, item_id)
    resource = _find_resource(item, resource_id)
    item.resources.remove(resource)
    save_course(course)
