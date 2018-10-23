import graphene
import graphql_jwt
from graphene_django import DjangoConnectionField
from graphene_django.filter import DjangoFilterConnectionField
from graphql_jwt.decorators import login_required, permission_required

from .account.mutations import (
    CustomerCreate, CustomerUpdate, CustomerPasswordReset, CustomerRegister,
    PasswordReset, SetPassword, StaffCreate, StaffDelete, StaffUpdate,
    AddressCreate, AddressUpdate, AddressDelete)
from .account.types import AddressValidationData, AddressValidationInput, User
from .account.resolvers import (
    resolve_address_validator, resolve_customers, resolve_staff_users)
from .core.types import TaxedMoney, ReportingPeriod
from .menu.resolvers import resolve_menu, resolve_menus, resolve_menu_items
from .menu.types import Menu, MenuItem
# FIXME: sorting import by putting below line at the beginning breaks app
from .menu.mutations import (
    AssignNavigation, MenuCreate, MenuDelete, MenuUpdate, MenuItemCreate,
    MenuItemDelete, MenuItemUpdate)
from .descriptions import DESCRIPTIONS
from .discount.resolvers import resolve_sales, resolve_vouchers
from .discount.types import Sale, Voucher
from .discount.mutations import (
    SaleCreate, SaleDelete, SaleUpdate, VoucherCreate, VoucherDelete,
    VoucherUpdate)
from .core.mutations import CreateToken, VerifyToken
from .order.resolvers import (
    resolve_order, resolve_orders, resolve_orders_total,
    resolve_homepage_events)
from .order.types import Order, OrderStatusFilter, OrderEvent
from .order.mutations.draft_orders import (
    DraftOrderComplete, DraftOrderCreate, DraftOrderDelete,
    DraftOrderLineCreate, DraftOrderLineDelete, DraftOrderLineUpdate,
    DraftOrderUpdate)
from .order.mutations.fulfillments import (
    FulfillmentCancel, FulfillmentCreate, FulfillmentUpdateTracking)
from .order.mutations.orders import (
    OrderAddNote, OrderCancel, OrderCapture, OrderMarkAsPaid, OrderRefund,
    OrderRelease, OrderUpdate, OrderUpdateShipping)
from .page.resolvers import resolve_pages, resolve_page
from .page.types import Page
from .page.mutations import PageCreate, PageDelete, PageUpdate
from .product.schema import ProductMutations, ProductQueries
from .shipping.resolvers import resolve_shipping_zones
from .shipping.types import ShippingZone
from .shipping.mutations import (
    ShippingZoneCreate, ShippingZoneDelete, ShippingZoneUpdate,
    ShippingPriceCreate, ShippingPriceDelete, ShippingPriceUpdate)
from .shop.types import Shop
from .shop.mutations import (
    AuthorizationKeyAdd, AuthorizationKeyDelete, ShopDomainUpdate,
    ShopSettingsUpdate, HomepageCollectionUpdate)


class Query(ProductQueries):
    address_validator = graphene.Field(
        AddressValidationData,
        input=graphene.Argument(AddressValidationInput, required=True))
    menu = graphene.Field(
        Menu, id=graphene.Argument(graphene.ID),
        name=graphene.Argument(graphene.String, description="Menu name."),
        description='Lookup a menu by ID or name.')
    menus = DjangoFilterConnectionField(
        Menu, query=graphene.String(description=DESCRIPTIONS['menu']),
        description="List of the shop\'s menus.")
    menu_item = graphene.Field(
        MenuItem, id=graphene.Argument(graphene.ID),
        description='Lookup a menu item by ID.')
    menu_items = DjangoFilterConnectionField(
        MenuItem, query=graphene.String(description=DESCRIPTIONS['menu_item']),
        description='List of the shop\'s menu items.')
    order = graphene.Field(
        Order, description='Lookup an order by ID.',
        id=graphene.Argument(graphene.ID))
    orders_total = graphene.Field(
        TaxedMoney, description='Total sales.',
        period=graphene.Argument(
            ReportingPeriod,
            description='Get total sales for selected span of time.'))
    orders = DjangoConnectionField(
        Order,
        query=graphene.String(description=DESCRIPTIONS['order']),
        created=graphene.Argument(
            ReportingPeriod,
            description='Filter orders from a selected timespan.'),
        status=graphene.Argument(
            OrderStatusFilter, description='Filter order by status'),
        description='List of the shop\'s orders.')
    homepage_events = DjangoConnectionField(
        OrderEvent, description='''List of activity events to display on
        homepage (at the moment it only contains order-events).''')
    page = graphene.Field(
        Page, id=graphene.Argument(graphene.ID), slug=graphene.String(),
        description='Lookup a page by ID or by slug.')
    pages = DjangoFilterConnectionField(
        Page, query=graphene.String(
            description=DESCRIPTIONS['page']),
        description='List of the shop\'s pages.')
    sale = graphene.Field(
        Sale, id=graphene.Argument(graphene.ID),
        description='Lookup a sale by ID.')
    sales = DjangoFilterConnectionField(
        Sale, query=graphene.String(description=DESCRIPTIONS['sale']),
        description="List of the shop\'s sales.")
    shop = graphene.Field(Shop, description='Represents a shop resources.')
    voucher = graphene.Field(
        Voucher, id=graphene.Argument(graphene.ID),
        description='Lookup a voucher by ID.')
    vouchers = DjangoFilterConnectionField(
        Voucher, query=graphene.String(description=DESCRIPTIONS['product']),
        description="List of the shop\'s vouchers.")
    shipping_zone = graphene.Field(
        ShippingZone, id=graphene.Argument(graphene.ID),
        description='Lookup a shipping zone by ID.')
    shipping_zones = DjangoFilterConnectionField(
        ShippingZone, description='List of the shop\'s shipping zones.')
    user = graphene.Field(
        User, id=graphene.Argument(graphene.ID),
        description='Lookup an user by ID.')
    customers = DjangoFilterConnectionField(
        User, description='List of the shop\'s users.',
        query=graphene.String(
            description=DESCRIPTIONS['user']))
    staff_users = DjangoFilterConnectionField(
        User, description='List of the shop\'s staff users.',
        query=graphene.String(description=DESCRIPTIONS['user']))
    node = graphene.Node.Field()

    @permission_required(['account.manage_users'])
    def resolve_user(self, info, id):
        return graphene.Node.get_node_from_global_id(info, id, User)

    @permission_required('account.manage_users')
    def resolve_customers(self, info, query=None, **kwargs):
        return resolve_customers(info, query=query)

    @permission_required('account.manage_staff')
    def resolve_staff_users(self, info, query=None, **kwargs):
        return resolve_staff_users(info, query=query)

    def resolve_menu(self, info, id=None, name=None):
        return resolve_menu(info, id, name)

    def resolve_menus(self, info, query=None, **kwargs):
        return resolve_menus(info, query)

    def resolve_menu_item(self, info, id):
        return graphene.Node.get_node_from_global_id(info, id, MenuItem)

    def resolve_menu_items(self, info, query=None, **kwargs):
        return resolve_menu_items(info, query)

    def resolve_page(self, info, id=None, slug=None):
        return resolve_page(info, id, slug)

    def resolve_pages(self, info, query=None, **kwargs):
        return resolve_pages(info, query=query)

    @login_required
    def resolve_order(self, info, id):
        return resolve_order(info, id)

    @permission_required('order.manage_orders')
    def resolve_orders_total(self, info, period, **kwargs):
        return resolve_orders_total(info, period)

    @login_required
    def resolve_orders(
            self, info, created=None, status=None, query=None, **kwargs):
        return resolve_orders(info, created, status, query)

    @permission_required('order.manage_orders')
    def resolve_homepage_events(self, info, **kwargs):
        return resolve_homepage_events(info)

    def resolve_shop(self, info):
        return Shop()

    @permission_required('discount.manage_discounts')
    def resolve_sale(self, info, id):
        return graphene.Node.get_node_from_global_id(info, id, Sale)

    @permission_required('discount.manage_discounts')
    def resolve_sales(self, info, query=None, **kwargs):
        return resolve_sales(info, query)

    @permission_required('discount.manage_discounts')
    def resolve_voucher(self, info, id):
        return graphene.Node.get_node_from_global_id(info, id, Voucher)

    @permission_required('discount.manage_discounts')
    def resolve_vouchers(self, info, query=None, **kwargs):
        return resolve_vouchers(info, query)

    @permission_required('shipping.manage_shipping')
    def resolve_shipping_zone(self, info, id):
        return graphene.Node.get_node_from_global_id(info, id, ShippingZone)

    @permission_required('shipping.manage_shipping')
    def resolve_shipping_zones(self, info, **kwargs):
        return resolve_shipping_zones(info)

    def resolve_address_validator(self, info, input):
        return resolve_address_validator(info, input)


class Mutations(ProductMutations):
    authorization_key_add = AuthorizationKeyAdd.Field()
    authorization_key_delete = AuthorizationKeyDelete.Field()

    assign_navigation = AssignNavigation.Field()

    token_create = CreateToken.Field()
    token_refresh = graphql_jwt.Refresh.Field()
    token_verify = VerifyToken.Field()

    set_password = SetPassword.Field()
    password_reset = PasswordReset.Field()

    customer_create = CustomerCreate.Field()
    customer_update = CustomerUpdate.Field()
    customer_password_reset = CustomerPasswordReset.Field()
    customer_register = CustomerRegister.Field()

    staff_create = StaffCreate.Field()
    staff_update = StaffUpdate.Field()
    staff_delete = StaffDelete.Field()

    address_create = AddressCreate.Field()
    address_update = AddressUpdate.Field()
    address_delete = AddressDelete.Field()

    menu_create = MenuCreate.Field()
    menu_delete = MenuDelete.Field()
    menu_update = MenuUpdate.Field()

    menu_item_create = MenuItemCreate.Field()
    menu_item_delete = MenuItemDelete.Field()
    menu_item_update = MenuItemUpdate.Field()

    draft_order_create = DraftOrderCreate.Field()
    draft_order_complete = DraftOrderComplete.Field()
    draft_order_delete = DraftOrderDelete.Field()
    draft_order_line_create = DraftOrderLineCreate.Field()
    draft_order_line_delete = DraftOrderLineDelete.Field()
    draft_order_line_update = DraftOrderLineUpdate.Field()
    draft_order_update = DraftOrderUpdate.Field()
    order_fulfillment_cancel = FulfillmentCancel.Field()
    order_fulfillment_create = FulfillmentCreate.Field()
    order_fulfillment_update_tracking = FulfillmentUpdateTracking.Field()
    order_add_note = OrderAddNote.Field()
    order_cancel = OrderCancel.Field()
    order_capture = OrderCapture.Field()
    order_mark_as_paid = OrderMarkAsPaid.Field()
    order_update_shipping = OrderUpdateShipping.Field()
    order_refund = OrderRefund.Field()
    order_release = OrderRelease.Field()
    order_update = OrderUpdate.Field()

    page_create = PageCreate.Field()
    page_delete = PageDelete.Field()
    page_update = PageUpdate.Field()

    sale_create = SaleCreate.Field()
    sale_delete = SaleDelete.Field()
    sale_update = SaleUpdate.Field()

    shop_domain_update = ShopDomainUpdate.Field()
    shop_settings_update = ShopSettingsUpdate.Field()
    homepage_collection_update = HomepageCollectionUpdate.Field()

    voucher_create = VoucherCreate.Field()
    voucher_delete = VoucherDelete.Field()
    voucher_update = VoucherUpdate.Field()

    shipping_zone_create = ShippingZoneCreate.Field()
    shipping_zone_delete = ShippingZoneDelete.Field()
    shipping_zone_update = ShippingZoneUpdate.Field()

    shipping_price_create = ShippingPriceCreate.Field()
    shipping_price_delete = ShippingPriceDelete.Field()
    shipping_price_update = ShippingPriceUpdate.Field()


schema = graphene.Schema(Query, Mutations)
