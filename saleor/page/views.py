import datetime

from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from .utils import pages_visible_to_user


def page_detail(request, url):
    page = get_object_or_404(
        pages_visible_to_user(user=request.user).filter(url=url))
    today = datetime.date.today()
    is_visible = (
        page.available_on is None or page.available_on <= today)
    return TemplateResponse(
        request, 'page/details.html', {
            'page': page, 'is_visible': is_visible})
