import graphene
import graphene_django_optimizer as gql_optimizer
from django.contrib.auth import get_user_model, models as auth_models
from graphene import relay
from graphene_federation import key
from graphql_jwt.exceptions import PermissionDenied

from ...account import models
from ...checkout.utils import get_user_checkout
from ...core.permissions import AccountPermissions, OrderPermissions, get_permissions
from ...order import models as order_models
from ..checkout.types import Checkout
from ..core.connection import CountableDjangoObjectType
from ..core.fields import PrefetchingConnectionField
from ..core.types import CountryDisplay, Image, PermissionDisplay
from ..core.utils import get_node_optimized
from ..decorators import one_of_permissions_required, permission_required
from ..meta.deprecated.resolvers import resolve_meta, resolve_private_meta
from ..meta.types import ObjectWithMetadata
from ..utils import format_permissions_for_display
from ..wishlist.resolvers import resolve_wishlist_items_from_user
from .enums import CountryCodeEnum, CustomerEventsEnum


class AddressInput(graphene.InputObjectType):
    first_name = graphene.String(description="Given name.")
    last_name = graphene.String(description="Family name.")
    company_name = graphene.String(description="Company or organization.")
    street_address_1 = graphene.String(description="Address.")
    street_address_2 = graphene.String(description="Address.")
    city = graphene.String(description="City.")
    city_area = graphene.String(description="District.")
    postal_code = graphene.String(description="Postal code.")
    country = CountryCodeEnum(description="Country.")
    country_area = graphene.String(description="State or province.")
    phone = graphene.String(description="Phone number.")


@key(fields="id")
class Address(CountableDjangoObjectType):
    country = graphene.Field(
        CountryDisplay, required=True, description="Shop's default country."
    )
    is_default_shipping_address = graphene.Boolean(
        required=False, description="Address is user's default shipping address."
    )
    is_default_billing_address = graphene.Boolean(
        required=False, description="Address is user's default billing address."
    )

    class Meta:
        description = "Represents user address data."
        interfaces = [relay.Node]
        model = models.Address
        only_fields = [
            "city",
            "city_area",
            "company_name",
            "country",
            "country_area",
            "first_name",
            "id",
            "last_name",
            "phone",
            "postal_code",
            "street_address_1",
            "street_address_2",
        ]

    @staticmethod
    def resolve_country(root: models.Address, _info):
        return CountryDisplay(code=root.country.code, country=root.country.name)

    @staticmethod
    def resolve_is_default_shipping_address(root: models.Address, _info):
        """Look if the address is the default shipping address of the user.

        This field is added through annotation when using the
        `resolve_addresses` resolver. It's invalid for
        `resolve_default_shipping_address` and
        `resolve_default_billing_address`
        """
        if not hasattr(root, "user_default_shipping_address_pk"):
            return None

        user_default_shipping_address_pk = getattr(
            root, "user_default_shipping_address_pk"
        )
        if user_default_shipping_address_pk == root.pk:
            return True
        return False

    @staticmethod
    def resolve_is_default_billing_address(root: models.Address, _info):
        """Look if the address is the default billing address of the user.

        This field is added through annotation when using the
        `resolve_addresses` resolver. It's invalid for
        `resolve_default_shipping_address` and
        `resolve_default_billing_address`
        """
        if not hasattr(root, "user_default_billing_address_pk"):
            return None

        user_default_billing_address_pk = getattr(
            root, "user_default_billing_address_pk"
        )
        if user_default_billing_address_pk == root.pk:
            return True
        return False

    @staticmethod
    def __resolve_reference(root, _info, **_kwargs):
        return graphene.Node.get_node_from_global_id(_info, root.id)


class CustomerEvent(CountableDjangoObjectType):
    date = graphene.types.datetime.DateTime(
        description="Date when event happened at in ISO 8601 format."
    )
    type = CustomerEventsEnum(description="Customer event type.")
    user = graphene.Field(lambda: User, description="User who performed the action.")
    message = graphene.String(description="Content of the event.")
    count = graphene.Int(description="Number of objects concerned by the event.")
    order = gql_optimizer.field(
        graphene.Field(
            "saleor.graphql.order.types.Order", description="The concerned order."
        ),
        model_field="order",
    )
    order_line = graphene.Field(
        "saleor.graphql.order.types.OrderLine", description="The concerned order line."
    )

    class Meta:
        description = "History log of the customer."
        model = models.CustomerEvent
        interfaces = [relay.Node]
        only_fields = ["id"]

    @staticmethod
    def resolve_user(root: models.CustomerEvent, info):
        user = info.context.user
        if (
            user == root.user
            or user.has_perm(AccountPermissions.MANAGE_USERS)
            or user.has_perm(AccountPermissions.MANAGE_STAFF)
        ):
            return root.user
        raise PermissionDenied()

    @staticmethod
    def resolve_message(root: models.CustomerEvent, _info):
        return root.parameters.get("message", None)

    @staticmethod
    def resolve_count(root: models.CustomerEvent, _info):
        return root.parameters.get("count", None)

    @staticmethod
    def resolve_order_line(root: models.CustomerEvent, info):
        if "order_line_pk" in root.parameters:
            try:
                qs = order_models.OrderLine.objects
                order_line_pk = root.parameters["order_line_pk"]
                return get_node_optimized(qs, {"pk": order_line_pk}, info)
            except order_models.OrderLine.DoesNotExist:
                pass
        return None


class ServiceAccountToken(CountableDjangoObjectType):
    name = graphene.String(description="Name of the authenticated token.")
    auth_token = graphene.String(description="Last 4 characters of the token.")

    class Meta:
        description = "Represents token data."
        model = models.ServiceAccountToken
        interfaces = [relay.Node]
        permissions = (AccountPermissions.MANAGE_SERVICE_ACCOUNTS,)
        only_fields = ["name", "auth_token"]

    @staticmethod
    def resolve_auth_token(root: models.ServiceAccountToken, _info, **_kwargs):
        return root.auth_token[-4:]


@key(fields="id")
class ServiceAccount(CountableDjangoObjectType):
    permissions = graphene.List(
        PermissionDisplay, description="List of the service's permissions."
    )
    created = graphene.DateTime(
        description="The date and time when the service account was created."
    )
    is_active = graphene.Boolean(
        description="Determine if service account will be set active or not."
    )
    name = graphene.String(description="Name of the service account.")

    tokens = graphene.List(
        ServiceAccountToken, description="Last 4 characters of the tokens."
    )

    class Meta:
        description = "Represents service account data."
        interfaces = [relay.Node, ObjectWithMetadata]
        model = models.ServiceAccount
        permissions = (AccountPermissions.MANAGE_SERVICE_ACCOUNTS,)
        only_fields = [
            "name",
            "permissions",
            "created",
            "is_active",
            "tokens",
            "id",
            "tokens",
        ]

    @staticmethod
    def resolve_permissions(root: models.ServiceAccount, _info, **_kwargs):
        permissions = root.permissions.prefetch_related("content_type").order_by(
            "codename"
        )
        return format_permissions_for_display(permissions)

    @staticmethod
    @gql_optimizer.resolver_hints(prefetch_related="tokens")
    def resolve_tokens(root: models.ServiceAccount, _info, **_kwargs):
        return root.tokens.all()

    @staticmethod
    def resolve_meta(root: models.ServiceAccount, info):
        return resolve_meta(root, info)

    @staticmethod
    def resolve_private_meta(root: models.ServiceAccount, _info):
        return resolve_private_meta(root, _info)

    @staticmethod
    def __resolve_reference(root, _info, **_kwargs):
        return graphene.Node.get_node_from_global_id(_info, root.id)


@key("id")
@key("email")
class User(CountableDjangoObjectType):
    addresses = gql_optimizer.field(
        graphene.List(Address, description="List of all user's addresses."),
        model_field="addresses",
    )
    checkout = graphene.Field(
        Checkout, description="Returns the last open checkout of this user."
    )
    gift_cards = gql_optimizer.field(
        PrefetchingConnectionField(
            "saleor.graphql.giftcard.types.GiftCard",
            description="List of the user gift cards.",
        ),
        model_field="gift_cards",
    )
    note = graphene.String(description="A note about the customer.")
    orders = gql_optimizer.field(
        PrefetchingConnectionField(
            "saleor.graphql.order.types.Order", description="List of user's orders."
        ),
        model_field="orders",
    )
    permissions = graphene.List(
        PermissionDisplay, description="List of user's permissions."
    )
    avatar = graphene.Field(Image, size=graphene.Int(description="Size of the avatar."))
    events = gql_optimizer.field(
        graphene.List(
            CustomerEvent, description="List of events associated with the user."
        ),
        model_field="events",
    )
    stored_payment_sources = graphene.List(
        "saleor.graphql.payment.types.PaymentSource",
        description="List of stored payment sources.",
    )

    class Meta:
        description = "Represents user data."
        interfaces = [relay.Node, ObjectWithMetadata]
        model = get_user_model()
        only_fields = [
            "date_joined",
            "default_billing_address",
            "default_shipping_address",
            "email",
            "first_name",
            "id",
            "is_active",
            "is_staff",
            "last_login",
            "last_name",
            "note",
        ]

    @staticmethod
    def resolve_addresses(root: models.User, _info, **_kwargs):
        return root.addresses.annotate_default(root).all()

    @staticmethod
    def resolve_checkout(root: models.User, _info, **_kwargs):
        return get_user_checkout(root)[0]

    @staticmethod
    def resolve_gift_cards(root: models.User, info, **_kwargs):
        return root.gift_cards.all()

    @staticmethod
    def resolve_permissions(root: models.User, _info, **_kwargs):
        if root.is_superuser:
            permissions = get_permissions()
        else:
            permissions = root.user_permissions.prefetch_related(
                "content_type"
            ).order_by("codename")
        return format_permissions_for_display(permissions)

    @staticmethod
    @one_of_permissions_required(
        [AccountPermissions.MANAGE_USERS, AccountPermissions.MANAGE_STAFF]
    )
    def resolve_note(root: models.User, info):
        return root.note

    @staticmethod
    @one_of_permissions_required(
        [AccountPermissions.MANAGE_USERS, AccountPermissions.MANAGE_STAFF]
    )
    def resolve_events(root: models.User, info):
        return root.events.all()

    @staticmethod
    def resolve_orders(root: models.User, info, **_kwargs):
        viewer = info.context.user
        if viewer.has_perm(OrderPermissions.MANAGE_ORDERS):
            return root.orders.all()
        return root.orders.confirmed()

    @staticmethod
    def resolve_avatar(root: models.User, info, size=None, **_kwargs):
        if root.avatar:
            return Image.get_adjusted(
                image=root.avatar,
                alt=None,
                size=size,
                rendition_key_set="user_avatars",
                info=info,
            )

    @staticmethod
    def resolve_stored_payment_sources(root: models.User, info):
        from .resolvers import resolve_payment_sources

        if root == info.context.user:
            return resolve_payment_sources(root)
        raise PermissionDenied()

    @staticmethod
    @one_of_permissions_required(
        [AccountPermissions.MANAGE_USERS, AccountPermissions.MANAGE_STAFF]
    )
    def resolve_private_meta(root: models.User, _info):
        return resolve_private_meta(root, _info)

    @staticmethod
    def resolve_meta(root: models.User, _info):
        return resolve_meta(root, _info)

    @staticmethod
    def resolve_wishlist(root: models.User, info, **_kwargs):
        return resolve_wishlist_items_from_user(root)

    @staticmethod
    def __resolve_reference(root, _info, **_kwargs):
        if root.id is not None:
            return graphene.Node.get_node_from_global_id(_info, root.id)
        return get_user_model().objects.get(email=root.email)


class ChoiceValue(graphene.ObjectType):
    raw = graphene.String()
    verbose = graphene.String()


class AddressValidationData(graphene.ObjectType):
    country_code = graphene.String()
    country_name = graphene.String()
    address_format = graphene.String()
    address_latin_format = graphene.String()
    allowed_fields = graphene.List(graphene.String)
    required_fields = graphene.List(graphene.String)
    upper_fields = graphene.List(graphene.String)
    country_area_type = graphene.String()
    country_area_choices = graphene.List(ChoiceValue)
    city_type = graphene.String()
    city_choices = graphene.List(ChoiceValue)
    city_area_type = graphene.String()
    city_area_choices = graphene.List(ChoiceValue)
    postal_code_type = graphene.String()
    postal_code_matchers = graphene.List(graphene.String)
    postal_code_examples = graphene.List(graphene.String)
    postal_code_prefix = graphene.String()


class StaffNotificationRecipient(CountableDjangoObjectType):
    user = graphene.Field(
        User,
        description="Returns a user subscribed to email notifications.",
        required=False,
    )
    email = graphene.String(
        description=(
            "Returns email address of a user subscribed to email notifications."
        ),
        required=False,
    )
    active = graphene.Boolean(description="Determines if a notification active.")

    class Meta:
        description = (
            "Represents a recipient of email notifications send by Saleor, "
            "such as notifications about new orders. Notifications can be "
            "assigned to staff users or arbitrary email addresses."
        )
        interfaces = [relay.Node]
        model = models.StaffNotificationRecipient
        only_fields = ["user", "active"]

    @staticmethod
    def resolve_user(root: models.StaffNotificationRecipient, info):
        user = info.context.user
        if user == root.user or user.has_perm(AccountPermissions.MANAGE_STAFF):
            return root.user
        raise PermissionDenied()

    @staticmethod
    def resolve_email(root: models.StaffNotificationRecipient, _info):
        return root.get_email()


@key(fields="id")
class Group(CountableDjangoObjectType):
    users = graphene.List(User, description="List of group users")
    permissions = graphene.List(
        PermissionDisplay, description="List of group permissions"
    )

    class Meta:
        description = ""
        interfaces = [relay.Node]
        model = auth_models.Group
        only_fields = ["name", "permissions", "users", "id"]

    @staticmethod
    @permission_required(AccountPermissions.MANAGE_STAFF)
    @gql_optimizer.resolver_hints(prefetch_related="user_set")
    def resolve_users(root: auth_models.Group, _info):
        return root.user_set.all()

    @staticmethod
    @gql_optimizer.resolver_hints(prefetch_related="permissions")
    def resolve_permissions(root: auth_models.Group, _info):
        permissions = root.permissions.prefetch_related("content_type").order_by(
            "codename"
        )
        return format_permissions_for_display(permissions)
