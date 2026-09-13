from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import SessionDep
from app.models import (
    Message,
    NavigationMenuItemCreate,
    NavigationMenuItemPublic,
    NavigationMenuItemsPublic,
    NavigationMenuItemUpdate,
)

router = APIRouter(prefix="/navigation-menu-items", tags=["navigation"])


@router.get("/", response_model=NavigationMenuItemsPublic)
def read_navigation_items(
    session: SessionDep, skip: int = 0, limit: int = 100, visible_only: bool = False
) -> Any:
    """List navigation menu items (optionally visible only)."""
    items, count = crud.get_navigation_menu_items(
        session=session, skip=skip, limit=limit, visible_only=visible_only
    )
    return NavigationMenuItemsPublic(
        data=[NavigationMenuItemPublic.model_validate(i) for i in items], count=count
    )


@router.post("/", response_model=NavigationMenuItemPublic)
def create_navigation_item(
    session: SessionDep, item_in: NavigationMenuItemCreate
) -> Any:
    """Create a navigation menu item."""
    return crud.create_navigation_menu_item(session=session, item_in=item_in)


@router.put("/{id}", response_model=NavigationMenuItemPublic)
def update_navigation_item(
    session: SessionDep, id: int, item_in: NavigationMenuItemUpdate
) -> Any:
    """Update a navigation menu item."""
    item = crud.get_navigation_menu_item(session=session, item_id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Navigation item not found")
    return crud.update_navigation_menu_item(
        session=session, db_item=item, item_in=item_in
    )


@router.delete("/{id}")
def delete_navigation_item(session: SessionDep, id: int) -> Message:
    """Delete a navigation menu item."""
    item = crud.get_navigation_menu_item(session=session, item_id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Navigation item not found")
    crud.delete_navigation_menu_item(session=session, db_item=item)
    return Message(message="Navigation item deleted successfully")
