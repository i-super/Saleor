from .....account import models
from ....core.doc_category import DOC_CATEGORY_USERS
from ....core.types import AccountError
from ...types import Address
from ..base import BaseAddressUpdate


class AccountAddressUpdate(BaseAddressUpdate):
    class Meta:
        auto_permission_message = False
        description = (
            "Updates an address of the logged-in user. Requires one of the following "
            "permissions: MANAGE_USERS, IS_OWNER."
        )
        doc_category = DOC_CATEGORY_USERS
        error_type_class = AccountError
        error_type_field = "account_errors"
        model = models.Address
        object_type = Address
