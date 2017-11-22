from django_elasticsearch_dsl import DocType, Index, fields
from elasticsearch_dsl import analyzer
from ..product.models import Product
from ..userprofile.models import User
from ..order.models import Order

storefront = Index('storefront')
storefront.settings(number_of_shards=1, number_of_replicas=0)


@storefront.doc_type
class ProductDocument(DocType):
    class Meta:
        model = Product  # The model associated with this DocType

        # The fields of the model you want to be indexed in Elasticsearch
        fields = [
            'name',
            'description',
            'is_published'
        ]


users = Index('users')
users.settings(number_of_shards=1, number_of_replicas=0)


email_analyzer = analyzer('email_analyzer', tokenizer='uax_url_email')


@users.doc_type
class UserDocument(DocType):
    user = fields.StringField(analyzer=email_analyzer)
    first_name = fields.StringField()
    last_name = fields.StringField()

    def prepare_user(self, instance):
        return instance.email

    def prepare_first_name(self, instance):
        address = instance.default_billing_address
        if address:
            return address.first_name

    def prepare_last_name(self, instance):
        address = instance.default_billing_address
        if address:
            return address.last_name

    class Meta:
        model = User
        fields = ['email']


orders = Index('orders')
orders.settings(number_of_shards=1, number_of_replicas=0)


@orders.doc_type
class OrderDocument(DocType):
    user = fields.StringField(analyzer=email_analyzer)

    def prepare_user(self, instance):
        if instance.user:
            return instance.user.email
        else:
            return instance.user_email

    class Meta:
        model = Order
        fields = ['status', 'user_email', 'discount_name']
