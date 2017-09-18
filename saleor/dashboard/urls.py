from django.conf.urls import url, include

from . import views as core_views
from .category.urls import urlpatterns as category_urls
from .customer.urls import urlpatterns as customer_urls
from .staff.urls import urlpatterns as staff_urls
from .group.urls import urlpatterns as groups_urls
from .order.urls import urlpatterns as order_urls
from .product.urls import urlpatterns as product_urls
from .discount.urls import urlpatterns as discount_urls
from .search.urls import urlpatterns as search_urls
from .sites.urls import urlpatterns as site_urls
from .shipping.urls import urlpatterns as shipping_urls


urlpatterns = [
    url(r'^$', core_views.index, name='index'),
    url(r'^categories/', include(category_urls)),
    url(r'^orders/', include(order_urls)),
    url(r'^products/', include(product_urls)),
    url(r'^customers/', include(customer_urls)),
    url(r'^staff/', include(staff_urls)),
    url(r'^groups/', include(groups_urls)),
    url(r'^discounts/', include(discount_urls)),
    url(r'^search/', include(search_urls)),
    url(r'^settings/', include(site_urls)),
    url(r'^shipping/', include(shipping_urls)),
    url(r'^style-guide/', core_views.styleguide, name='styleguide'),
]
