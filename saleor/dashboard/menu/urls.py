from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$',
        views.menu_list, name='menu-list'),
    url(r'^add/$',
        views.menu_create, name='menu-add'),
    url(r'^(?P<pk>[0-9]+)/edit/$',
        views.menu_edit, name='menu-edit'),
    url(r'^(?P<pk>[0-9]+)/delete/$',
        views.menu_delete, name='menu-delete'),
    url(r'^(?P<pk>[0-9]+)/$',
        views.menu_detail, name='menu-detail'),

    url(r'^(?P<menu_pk>[0-9]+)/item/(?P<item_pk>[0-9]+)/$',
        views.menu_item_detail, name='menu-item-detail'),
    url(r'^(?P<menu_pk>[0-9]+)/add/$',
        views.menu_item_create, name='menu-item-add'),
    url(r'^(?P<menu_pk>[0-9]+)/item/(?P<root_pk>[0-9]+)/add/$',
        views.menu_item_create, name='menu-item-add'),
    url(r'^(?P<menu_pk>[0-9]+)/item/(?P<item_pk>[0-9]+)/edit/$',
        views.menu_item_edit, name='menu-item-edit'),
    url(r'^(?P<menu_pk>[0-9]+)/item/(?P<item_pk>[0-9]+)/delete/$',
        views.menu_item_delete, name='menu-item-delete'),
    url(r'^(?P<menu_pk>[0-9]+)/item/(?P<root_pk>[0-9]+)/items/reorder/$',
        views.ajax_reorder_menu_items, name='menu-items-reorder'),
    url(r'^(?P<menu_pk>[0-9]+)/items/reorder/$',
        views.ajax_reorder_menu_items, name='menu-items-reorder')]
