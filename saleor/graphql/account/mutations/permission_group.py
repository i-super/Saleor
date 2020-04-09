from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import graphene
from django.contrib.auth import models as auth_models
from django.core.exceptions import ValidationError
from django.db import transaction

from ....account.error_codes import PermissionGroupErrorCode
from ....core.permissions import AccountPermissions, get_permissions
from ...account.utils import (
    can_user_manage_group,
    get_not_manageable_permissions_after_group_deleting,
    get_not_manageable_permissions_after_removing_users_from_group,
    get_out_of_scope_permissions,
    get_out_of_scope_users,
)
from ...core.enums import PermissionEnum
from ...core.mutations import ModelDeleteMutation, ModelMutation
from ...core.types.common import PermissionGroupError
from ...core.utils import get_duplicates_ids
from ..types import Group

if TYPE_CHECKING:
    from ....account.models import User


class PermissionGroupCreateInput(graphene.InputObjectType):
    name = graphene.String(description="Group name.", required=True)
    permissions = graphene.List(
        graphene.NonNull(PermissionEnum),
        description="List of permission code names to assign to this group.",
        required=False,
    )
    users = graphene.List(
        graphene.NonNull(graphene.ID),
        description="List of users to assign to this group.",
        required=False,
    )


class PermissionGroupCreate(ModelMutation):
    group = graphene.Field(Group, description="The newly created group.")

    class Arguments:
        input = PermissionGroupCreateInput(
            description="Input fields to create permission group.", required=True
        )

    class Meta:
        description = "Create new permission group."
        model = auth_models.Group
        permissions = (AccountPermissions.MANAGE_STAFF,)
        error_type_class = PermissionGroupError
        error_type_field = "permission_group_errors"

    @classmethod
    @transaction.atomic
    def _save_m2m(cls, info, instance, cleaned_data):
        super()._save_m2m(info, instance, cleaned_data)
        users = cleaned_data.get("users")
        if users:
            instance.user_set.add(*users)

    @classmethod
    def clean_input(
        cls, info, instance, data,
    ):
        cleaned_input = super().clean_input(info, instance, data)
        requestor = info.context.user
        errors = defaultdict(list)
        cls.clean_permissions(requestor, errors, "permissions", cleaned_input)
        user_items = cleaned_input.get("users")
        if user_items:
            cls.can_manage_users(requestor, errors, "users", cleaned_input)
            cls.check_if_users_are_staff(errors, "users", cleaned_input)

        if errors:
            raise ValidationError(errors)

        return cleaned_input

    @classmethod
    def clean_permissions(
        cls,
        requestor: "User",
        errors: Dict[Optional[str], List[ValidationError]],
        field: str,
        cleaned_input: dict,
    ):
        permission_items = cleaned_input.get(field)
        if permission_items:
            cleaned_input[field] = get_permissions(cleaned_input[field])

            if requestor.is_superuser:
                return

            permissions = get_out_of_scope_permissions(requestor, permission_items)
            if permissions:
                # add error
                error_msg = "You can't add permission that you don't have."
                code = PermissionGroupErrorCode.OUT_OF_SCOPE_PERMISSION.value
                params = {"permissions": permissions}
                cls.update_errors(errors, error_msg, field, code, params)

    @classmethod
    def can_manage_users(
        cls,
        requestor: "User",
        errors: Dict[Optional[str], List[ValidationError]],
        field: str,
        cleaned_input: dict,
    ):
        """Check if requestor can manage users from input.

        Requestor cannot manage users with wider scope of permissions.
        """
        users = cleaned_input[field]
        if requestor.is_superuser:
            return
        out_of_scope_users = get_out_of_scope_users(requestor, users)
        if out_of_scope_users:
            # add error
            ids = [
                graphene.Node.to_global_id("User", user_instance.pk)
                for user_instance in out_of_scope_users
            ]
            error_msg = "You can't manage these users."
            code = PermissionGroupErrorCode.OUT_OF_SCOPE_USER.value
            params = {"users": ids}
            cls.update_errors(errors, error_msg, field, code, params)

    @classmethod
    def check_if_users_are_staff(
        cls,
        errors: Dict[Optional[str], List[ValidationError]],
        field: str,
        cleaned_input: dict,
    ):
        """Check if all of the users are staff members."""
        users = cleaned_input[field]
        non_staff_users = [user.pk for user in users if not user.is_staff]
        if non_staff_users:
            # add error
            ids = [graphene.Node.to_global_id("User", pk) for pk in non_staff_users]
            error_msg = "User must be staff member."
            code = PermissionGroupErrorCode.ASSIGN_NON_STAFF_MEMBER.value
            params = {"users": ids}
            cls.update_errors(errors, error_msg, field, code, params)

    @classmethod
    def update_errors(
        cls,
        errors: Dict[Optional[str], List[ValidationError]],
        msg: str,
        field: Optional[str],
        code: str,
        params: dict,
    ):
        """Create ValidationError and add it to error list."""
        error = ValidationError(message=msg, code=code, params=params)
        errors[field].append(error)


class PermissionGroupUpdateInput(graphene.InputObjectType):
    name = graphene.String(description="Group name.", required=False)
    add_permissions = graphene.List(
        graphene.NonNull(PermissionEnum),
        description="List of permission code names to assign to this group.",
        required=False,
    )
    remove_permissions = graphene.List(
        graphene.NonNull(PermissionEnum),
        description="List of permission code names to unassign from this group.",
        required=False,
    )
    add_users = graphene.List(
        graphene.NonNull(graphene.ID),
        description="List of users to assign to this group.",
        required=False,
    )
    remove_users = graphene.List(
        graphene.NonNull(graphene.ID),
        description="List of users to unassign from this group.",
        required=False,
    )


class PermissionGroupUpdate(PermissionGroupCreate):
    group = graphene.Field(Group, description="Group which was edited.")

    class Arguments:
        id = graphene.ID(description="ID of the group to update.", required=True)
        input = PermissionGroupUpdateInput(
            description="Input fields to create permission group.", required=True
        )

    class Meta:
        description = "Update permission group."
        model = auth_models.Group
        permissions = (AccountPermissions.MANAGE_STAFF,)
        error_type_class = PermissionGroupError
        error_type_field = "permission_group_errors"

    @classmethod
    @transaction.atomic
    def _save_m2m(cls, info, instance, cleaned_data):
        cls.update_group_permissions_and_users(instance, cleaned_data)

    @classmethod
    def update_group_permissions_and_users(
        cls, group: auth_models.Group, cleaned_input: dict
    ):
        add_users = cleaned_input.get("add_users")
        remove_users = cleaned_input.get("remove_users")
        if add_users:
            group.user_set.add(*add_users)
        if remove_users:
            group.user_set.remove(*remove_users)

        add_permissions = cleaned_input.get("add_permissions")
        remove_permissions = cleaned_input.get("remove_permissions")
        if add_permissions:
            group.permissions.add(*add_permissions)
        if remove_permissions:
            group.permissions.remove(*remove_permissions)

    @classmethod
    def clean_input(
        cls, info, instance, data,
    ):
        requestor = info.context.user
        if not requestor.is_superuser and not can_user_manage_group(
            requestor, instance
        ):
            error_msg = "You can't manage group with permissions out of your scope."
            code = PermissionGroupErrorCode.OUT_OF_SCOPE_PERMISSION.value
            raise ValidationError(error_msg, code)

        errors = defaultdict(list)
        permission_fields = ("add_permissions", "remove_permissions", "permissions")
        user_fields = ("add_users", "remove_users", "users")

        cls.check_for_duplicates(errors, data, permission_fields)
        cls.check_for_duplicates(errors, data, user_fields)

        cleaned_input = super().clean_input(info, instance, data)

        cls.clean_users(requestor, errors, cleaned_input, instance)
        cls.clean_permissions(requestor, errors, "add_permissions", cleaned_input)
        remove_permissions = cleaned_input.get("remove_permissions")
        if remove_permissions:
            cleaned_input["remove_permissions"] = get_permissions(remove_permissions)

        if errors:
            raise ValidationError(errors)

        return cleaned_input

    @classmethod
    def clean_users(
        cls, requestor: "User", errors: dict, cleaned_input: dict, group: Group
    ):
        add_users = cleaned_input.get("add_users")
        remove_users = cleaned_input.get("remove_users")
        if add_users:
            cls.can_manage_users(requestor, errors, "add_users", cleaned_input)
            cls.check_if_users_are_staff(errors, "add_users", cleaned_input)
        if remove_users:
            cls.can_manage_users(requestor, errors, "remove_users", cleaned_input)
            cls.clean_remove_users(requestor, errors, cleaned_input, group)

    @classmethod
    def clean_remove_users(
        cls, requestor: "User", errors: dict, cleaned_input: dict, group: Group
    ):
        cls.check_if_removing_user_last_group(requestor, errors, cleaned_input)
        cls.check_if_users_can_be_removed(requestor, errors, cleaned_input, group)

    @classmethod
    def check_if_removing_user_last_group(
        cls, requestor: "User", errors: dict, cleaned_input: dict
    ):
        """Ensure user doesn't remove user's last group."""
        remove_users = cleaned_input["remove_users"]
        if requestor in remove_users and requestor.groups.count() == 1:
            # add error
            error_msg = "You cannot remove yourself from your last group."
            code = PermissionGroupErrorCode.CANNOT_REMOVE_FROM_LAST_GROUP.value
            params = {"users": [graphene.Node.to_global_id("User", requestor.pk)]}
            cls.update_errors(errors, error_msg, "remove_users", code, params)

    @classmethod
    def check_if_users_can_be_removed(
        cls, requestor: "User", errors: dict, cleaned_input: dict, group: Group
    ):
        """Check if after removing users from group all permissions will be manageable.

        After removing users from group, for each permission, there should be
        at least one staff member who can manage it (has both “manage staff”
        and this permission).
        """
        if requestor.is_superuser:
            return

        remove_users = cleaned_input["remove_users"]
        add_users = cleaned_input.get("add_users")
        manage_staff_permission = AccountPermissions.MANAGE_STAFF.value

        # check if user with manage staff will be added to the group
        if add_users:
            if any([user.has_perm(manage_staff_permission) for user in add_users]):
                return True

        permissions = get_not_manageable_permissions_after_removing_users_from_group(
            group, remove_users
        )
        if permissions:
            # add error
            permission_codes = [PermissionEnum.get(code) for code in permissions]
            msg = "Users cannot be removed, some of permissions will not be manageable."
            code = PermissionGroupErrorCode.LEFT_NOT_MANAGEABLE_PERMISSION.value
            params = {"permissions": permission_codes}
            raise ValidationError(
                {"remove_users": ValidationError(message=msg, code=code, params=params)}
            )

    @classmethod
    def check_for_duplicates(
        cls, errors: dict, input_data: dict, fields: Tuple[str, str, str],
    ):
        """Check if any items are on both input field.

        Raise error if some of items are duplicated.
        """
        add_field, remove_field, error_class_field = fields
        duplicated_ids = get_duplicates_ids(
            input_data.get(add_field), input_data.get(remove_field)
        )
        if duplicated_ids:
            # add error
            error_msg = (
                "The same object cannot be in both list"
                "for adding and removing items."
            )
            code = PermissionGroupErrorCode.CANNOT_ADD_AND_REMOVE.value
            params = {error_class_field: list(duplicated_ids)}
            cls.update_errors(errors, error_msg, None, code, params)


class PermissionGroupDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(description="ID of the group to delete.", required=True)

    class Meta:
        description = "Delete permission group."
        model = auth_models.Group
        permissions = (AccountPermissions.MANAGE_STAFF,)
        error_type_class = PermissionGroupError
        error_type_field = "permission_group_errors"

    @classmethod
    def clean_instance(cls, info, instance):
        user = info.context.user
        if user.is_superuser:
            return
        if not can_user_manage_group(user, instance):
            error_msg = "You can't manage group with permissions out of your scope."
            code = PermissionGroupErrorCode.OUT_OF_SCOPE_PERMISSION.value
            raise ValidationError(error_msg, code)

        cls.check_if_group_can_be_removed(instance)

    @classmethod
    def check_if_group_can_be_removed(cls, group):
        """Return true if management of all permissions is provided by other groups.

        After removing group, for each permission, there should be at least one staff
        member who can manage it (has both “manage staff” and this permission).
        """
        permissions = get_not_manageable_permissions_after_group_deleting(group)
        if permissions:
            permission_codes = [PermissionEnum.get(code) for code in permissions]
            msg = "Group cannot be removed, some of permissions will not be manageable."
            code = PermissionGroupErrorCode.LEFT_NOT_MANAGEABLE_PERMISSION.value
            params = {"permissions": permission_codes}
            raise ValidationError(
                {"id": ValidationError(message=msg, code=code, params=params)}
            )
