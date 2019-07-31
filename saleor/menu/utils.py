from django.db import transaction
from django.db.models import Q

from ..menu.models import Menu, MenuItem
from ..page.models import Page
from ..product.models import Category, Collection


def update_menu_item_linked_object(menu_item, linked_object):
    """Assign new linked object to a menu item. Clear other links."""
    menu_item.category = None
    menu_item.collection = None
    menu_item.page = None

    if isinstance(linked_object, Category):
        menu_item.category = linked_object
    elif isinstance(linked_object, Collection):
        menu_item.collection = linked_object
    elif isinstance(linked_object, Page):
        menu_item.page = linked_object

    return menu_item.save()


def get_menus_that_need_update(collection=None, categories=None, page=None):
    """Return the primary keys of the Menu instances.

    They that will be affected by deleting one of the listed objects,
    therefore needs to be updated afterwards.
    """
    if not any([page, collection, categories]):
        return []
    q = Q()
    if collection is not None:
        q |= Q(collection=collection)
    if categories is not None:
        q |= Q(category__in=categories)
    if page is not None:
        q |= Q(page=page)
    menus_to_be_updated = (
        MenuItem.objects.filter(q).distinct().values_list("menu", flat=True)
    )
    return menus_to_be_updated


def get_menu_item_as_dict(menu_item):
    data = {}
    if menu_item.linked_object:
        data["url"] = menu_item.linked_object.get_absolute_url()
    else:
        data["url"] = menu_item.url
    data["name"] = menu_item.name
    data["translations"] = {
        translated.language_code: {"name": translated.name}
        for translated in menu_item.translations.all()
    }
    return data


def get_menu_as_json(menu):
    """Build a tree structure from top menu items, its children and grandchildren."""
    top_items = menu.items.filter(parent=None).prefetch_related(
        "category",
        "page",
        "collection",
        "children__category",
        "children__page",
        "children__collection",
        "children__children__category",
        "children__children__page",
        "children__children__collection",
        "translations",
        "children__translations",
        "children__children__translations",
    )
    menu_data = []
    for item in top_items:
        top_item_data = get_menu_item_as_dict(item)
        top_item_data["child_items"] = []
        children = item.children.all()
        for child in children:
            child_data = get_menu_item_as_dict(child)
            grand_children = child.children.all()
            grand_children_data = [
                get_menu_item_as_dict(grand_child) for grand_child in grand_children
            ]
            child_data["child_items"] = grand_children_data
            top_item_data["child_items"].append(child_data)
        menu_data.append(top_item_data)
    return menu_data


@transaction.atomic
def update_menus(menus_pk):
    menus = Menu.objects.filter(pk__in=menus_pk)
    for menu in menus:
        update_menu(menu)


def update_menu(menu):
    menu.json_content = get_menu_as_json(menu)
    menu.save(update_fields=["json_content"])
