from typing import Any

from sqlmodel import Session, col, func, select

from app.models import (
    NavigationMenuItem,
    NavigationMenuItemCreate,
    NavigationMenuItemUpdate,
)


def create_navigation_menu_item(
    *, session: Session, item_in: NavigationMenuItemCreate
) -> NavigationMenuItem:
    db_obj = NavigationMenuItem.model_validate(item_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_navigation_menu_item(
    *, session: Session, item_id: int
) -> NavigationMenuItem | None:
    return session.get(NavigationMenuItem, item_id)


def get_navigation_menu_items(
    *, session: Session, skip: int = 0, limit: int = 100, visible_only: bool = False
) -> tuple[list[NavigationMenuItem], int]:
    statement = select(NavigationMenuItem)
    count_statement = select(func.count()).select_from(NavigationMenuItem)
    if visible_only:
        statement = statement.where(col(NavigationMenuItem.is_visible))
        count_statement = count_statement.where(col(NavigationMenuItem.is_visible))
    count = session.exec(count_statement).one()
    statement = (
        statement.order_by(
            col(NavigationMenuItem.sort_order).asc(), col(NavigationMenuItem.id).asc()
        )
        .offset(skip)
        .limit(limit)
    )
    items = list(session.exec(statement).all())
    return items, count


def update_navigation_menu_item(
    *, session: Session, db_item: NavigationMenuItem, item_in: NavigationMenuItemUpdate
) -> Any:
    item_data = item_in.model_dump(exclude_unset=True)
    db_item.sqlmodel_update(item_data)
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


def delete_navigation_menu_item(
    *, session: Session, db_item: NavigationMenuItem
) -> None:
    session.delete(db_item)
    session.commit()
