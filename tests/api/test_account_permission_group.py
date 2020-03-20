import graphene
import pytest
from django.contrib.auth.models import Group

from saleor.account.error_codes import AccountErrorCode, PermissionGroupErrorCode
from saleor.account.models import User
from saleor.core.permissions import AccountPermissions, OrderPermissions

from .utils import assert_no_permission, get_graphql_content

PERMISSION_GROUP_CREATE_MUTATION = """
    mutation PermissionGroupCreate(
        $input: PermissionGroupCreateInput!) {
        permissionGroupCreate(
            input: $input)
        {
            group{
                id
                name
                permissions {
                    name
                    code
                }
                users {
                    email
                }
            }
            permissionGroupErrors{
                field
                code
                permissions
                users
                message
            }
        }
    }
    """


def test_permission_group_create_mutation(
    staff_users,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
    permission_manage_service_accounts,
):
    staff_user = staff_users[0]
    staff_user.user_permissions.add(
        permission_manage_users, permission_manage_service_accounts
    )
    query = PERMISSION_GROUP_CREATE_MUTATION

    variables = {
        "input": {
            "name": "New permission group",
            "permissions": [
                AccountPermissions.MANAGE_USERS.name,
                AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name,
            ],
            "users": [
                graphene.Node.to_global_id("User", user.id) for user in staff_users
            ],
        }
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupCreate"]
    permission_group_data = data["group"]

    group = Group.objects.get()
    assert permission_group_data["name"] == group.name == variables["input"]["name"]
    permissions = {
        permission["name"] for permission in permission_group_data["permissions"]
    }
    assert set(group.permissions.all().values_list("name", flat=True)) == permissions
    permissions_codes = {
        permission["code"].lower()
        for permission in permission_group_data["permissions"]
    }
    assert (
        set(group.permissions.all().values_list("codename", flat=True))
        == permissions_codes
        == set(perm.lower() for perm in variables["input"]["permissions"])
    )
    assert (
        {user["email"] for user in permission_group_data["users"]}
        == {user.email for user in staff_users}
        == set(group.user_set.all().values_list("email", flat=True))
    )
    assert data["permissionGroupErrors"] == []


def test_permission_group_create_mutation_lack_of_permission(
    staff_user, permission_manage_staff, staff_api_client, permission_manage_orders,
):
    staff_user.user_permissions.add(permission_manage_orders)
    query = PERMISSION_GROUP_CREATE_MUTATION

    variables = {
        "input": {
            "name": "New permission group",
            "permissions": [
                AccountPermissions.MANAGE_USERS.name,
                OrderPermissions.MANAGE_ORDERS.name,
                AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name,
            ],
        }
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupCreate"]

    errors = data["permissionGroupErrors"]
    assert len(errors) == 1
    assert errors[0]["field"] == "permissions"
    assert errors[0]["code"] == PermissionGroupErrorCode.OUT_OF_SCOPE_PERMISSION.name
    assert set(errors[0]["permissions"]) == {
        AccountPermissions.MANAGE_USERS.name,
        AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name,
    }
    assert errors[0]["users"] is None


def test_permission_group_create_mutation_group_exists(
    staff_user,
    permission_manage_staff,
    staff_api_client,
    permission_group_manage_users,
    permission_manage_users,
    permission_manage_service_accounts,
):
    staff_user.user_permissions.add(
        permission_manage_users, permission_manage_service_accounts
    )
    query = PERMISSION_GROUP_CREATE_MUTATION

    variables = {
        "input": {
            "name": permission_group_manage_users.name,
            "permissions": [
                AccountPermissions.MANAGE_USERS.name,
                AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name,
            ],
            "users": [graphene.Node.to_global_id("User", staff_user.id)],
        }
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupCreate"]
    errors = data["permissionGroupErrors"]
    permission_group_data = data["group"]

    assert permission_group_data is None
    assert len(errors) == 1
    assert errors[0]["field"] == "name"
    assert errors[0]["code"] == AccountErrorCode.UNIQUE.name
    assert errors[0]["permissions"] is None
    assert errors[0]["users"] is None


def test_permission_group_create_mutation_add_customer_user(
    staff_user,
    customer_user,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
    permission_manage_service_accounts,
):
    """Ensure creating permission group with customer user in input field for adding
    users failed. Mutations should failed. Error should contains list of wrong users
    IDs.
    """

    second_customer = User.objects.create(
        email="second_customer@test.com", password="test"
    )

    staff_user.user_permissions.add(
        permission_manage_users, permission_manage_service_accounts
    )
    query = PERMISSION_GROUP_CREATE_MUTATION

    user_ids = [
        graphene.Node.to_global_id("User", user.id)
        for user in [staff_user, customer_user, second_customer]
    ]
    variables = {
        "input": {
            "name": "New permission group",
            "permissions": [
                AccountPermissions.MANAGE_USERS.name,
                AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name,
            ],
            "users": user_ids,
        }
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupCreate"]
    errors = data["permissionGroupErrors"]

    assert errors
    assert len(errors) == 1
    assert errors[0]["field"] == "users"
    assert errors[0]["permissions"] is None
    assert set(errors[0]["users"]) == set(user_ids[1:])
    assert errors[0]["code"] == AccountErrorCode.ASSIGN_NON_STAFF_MEMBER.name
    assert data["group"] is None


def test_permission_group_create_mutation_lack_of_permission_and_customer_user(
    staff_user,
    customer_user,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
):
    staff_user.user_permissions.add(permission_manage_users)
    query = PERMISSION_GROUP_CREATE_MUTATION

    user_ids = [
        graphene.Node.to_global_id("User", user.id)
        for user in [staff_user, customer_user]
    ]
    variables = {
        "input": {
            "name": "New permission group",
            "permissions": [
                AccountPermissions.MANAGE_USERS.name,
                AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name,
            ],
            "users": user_ids,
        }
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupCreate"]
    errors = data["permissionGroupErrors"]

    assert errors
    assert len(errors) == 2
    assert {error["field"] for error in errors} == {"users", "permissions"}
    assert [AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name] in [
        error["permissions"] for error in errors
    ]
    assert user_ids[1:] in [error["users"] for error in errors]
    assert {error["code"] for error in errors} == {
        AccountErrorCode.ASSIGN_NON_STAFF_MEMBER.name,
        PermissionGroupErrorCode.OUT_OF_SCOPE_PERMISSION.name,
    }
    assert data["group"] is None


PERMISSION_GROUP_UPDATE_MUTATION = """
    mutation PermissionGroupUpdate(
        $id: ID!, $input: PermissionGroupUpdateInput!) {
        permissionGroupUpdate(
            id: $id, input: $input)
        {
            group{
                id
                name
                permissions {
                    name
                    code
                }
                users {
                    email
                }
            }
            permissionGroupErrors{
                field
                code
                permissions
                users
                message
            }
        }
    }
    """


def test_permission_group_update_mutation(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    staff_api_client,
    permission_manage_service_accounts,
    permission_manage_users,
):
    staff_user.user_permissions.add(
        permission_manage_service_accounts, permission_manage_users
    )
    group = permission_group_manage_users
    query = PERMISSION_GROUP_UPDATE_MUTATION

    # set of users emails being in a group
    users = set(group.user_set.values_list("email", flat=True))

    group_user = group.user_set.first()
    variables = {
        "id": graphene.Node.to_global_id("Group", group.id),
        "input": {
            "name": "New permission group",
            "addPermissions": [AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name],
            "removePermissions": [AccountPermissions.MANAGE_USERS.name],
            "addUsers": [graphene.Node.to_global_id("User", staff_user.pk)],
            "removeUsers": [graphene.Node.to_global_id("User", group_user.pk)],
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    permission_group_data = data["group"]

    # remove and add user email for comparing users set
    users.remove(group_user.email)
    users.add(staff_user.email)

    group = Group.objects.get()
    assert permission_group_data["name"] == group.name
    permissions = {
        permission["name"] for permission in permission_group_data["permissions"]
    }
    assert set(group.permissions.all().values_list("name", flat=True)) == permissions
    permissions_codes = {
        permission["code"].lower()
        for permission in permission_group_data["permissions"]
    }
    assert (
        set(group.permissions.all().values_list("codename", flat=True))
        == permissions_codes
    )
    assert set(group.user_set.all().values_list("email", flat=True)) == users
    assert data["permissionGroupErrors"] == []


def test_permission_group_update_mutation_remove_me_from_last_group(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
):
    """Ensure mutation failed when user removing himself from user's last group."""
    staff_user.user_permissions.add(permission_manage_users)
    group = permission_group_manage_users
    # ensure user is in group
    group.user_set.add(staff_user)
    assert staff_user.groups.count() == 1

    query = PERMISSION_GROUP_UPDATE_MUTATION

    staff_user_id = graphene.Node.to_global_id("User", staff_user.pk)
    variables = {
        "id": graphene.Node.to_global_id("Group", group.id),
        "input": {"removeUsers": [staff_user_id]},
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    permission_group_data = data["group"]
    errors = data["permissionGroupErrors"]

    assert not permission_group_data
    assert len(errors) == 1
    assert errors[0]["field"] == "removeUsers"
    assert (
        errors[0]["code"] == PermissionGroupErrorCode.CANNOT_REMOVE_FROM_LAST_GROUP.name
    )
    assert errors[0]["permissions"] is None
    assert errors[0]["users"] == [staff_user_id]
    assert staff_user.groups.count() == 1


def test_permission_group_update_mutation_remove_me_from_not_last_group(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
):
    """Ensure user can remove himself from group if he is a member of another group."""
    staff_user.user_permissions.add(permission_manage_users)
    group = permission_group_manage_users
    group2 = Group.objects.create(name="Test group")

    # ensure user is in group
    group.user_set.add(staff_user)
    group2.user_set.add(staff_user)

    assert staff_user.groups.count() == 2

    query = PERMISSION_GROUP_UPDATE_MUTATION

    staff_user_id = graphene.Node.to_global_id("User", staff_user.pk)
    variables = {
        "id": graphene.Node.to_global_id("Group", group.id),
        "input": {"removeUsers": [staff_user_id]},
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    permission_group_data = data["group"]
    errors = data["permissionGroupErrors"]

    assert not errors
    assert staff_user_id not in permission_group_data["users"]
    assert staff_user.groups.count() == 1


def test_permission_group_update_mutation_remove_last_user_from_group(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
):
    """Ensure user can remove last user from the group."""
    staff_user.user_permissions.add(permission_manage_users)
    group = permission_group_manage_users

    # ensure group contains only 1 user
    assert group.user_set.count() == 1

    group_user = group.user_set.first()

    query = PERMISSION_GROUP_UPDATE_MUTATION

    group_user_id = graphene.Node.to_global_id("User", group_user.pk)
    variables = {
        "id": graphene.Node.to_global_id("Group", group.id),
        "input": {"removeUsers": [group_user_id]},
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    permission_group_data = data["group"]
    errors = data["permissionGroupErrors"]

    assert not errors
    assert staff_user.groups.count() == 0
    assert permission_group_data["users"] == []


def test_permission_group_update_mutation_only_name(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
):
    """Ensure mutation update group when only name are passed in input."""
    staff_user.user_permissions.add(permission_manage_staff, permission_manage_users)
    group = permission_group_manage_users
    old_group_name = group.name
    query = PERMISSION_GROUP_UPDATE_MUTATION

    variables = {
        "id": graphene.Node.to_global_id("Group", group.id),
        "input": {"name": "New permission group"},
    }
    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    permission_group_data = data["group"]

    group = Group.objects.get()
    assert group.name != old_group_name
    assert permission_group_data["name"] == group.name
    assert group.permissions.all().count() == 1
    assert group.permissions.first() == permission_manage_users
    result_permissions = {
        permission["name"] for permission in permission_group_data["permissions"]
    }
    assert (
        set(group.permissions.all().values_list("name", flat=True))
        == result_permissions
    )
    permissions_codes = {
        permission["code"].lower()
        for permission in permission_group_data["permissions"]
    }
    assert (
        set(group.permissions.all().values_list("codename", flat=True))
        == permissions_codes
    )
    assert data["permissionGroupErrors"] == []


def test_permission_group_update_mutation_with_name_which_exists(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
):
    """Ensure mutation failed where updating name with value which already is a name of
    different group.
    """
    staff_user.user_permissions.add(permission_manage_staff, permission_manage_users)
    group = permission_group_manage_users
    old_group_name = group.name
    query = PERMISSION_GROUP_UPDATE_MUTATION

    new_name = "New permission group"
    Group.objects.create(name=new_name)

    variables = {
        "id": graphene.Node.to_global_id("Group", group.id),
        "input": {"name": new_name},
    }
    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    permission_group_data = data["group"]
    errors = data["permissionGroupErrors"]

    group.refresh_from_db()
    assert not permission_group_data
    assert len(errors) == 1
    assert errors[0]["field"] == "name"
    assert errors[0]["code"] == PermissionGroupErrorCode.UNIQUE.name
    assert errors[0]["permissions"] is None
    assert errors[0]["users"] is None
    assert group.name == old_group_name


def test_permission_group_update_mutation_only_permissions(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
    permission_manage_service_accounts,
):
    """Ensure mutation update group when only permissions are passed in input."""
    staff_user.user_permissions.add(
        permission_manage_users, permission_manage_service_accounts
    )
    group = permission_group_manage_users
    old_group_name = group.name
    query = PERMISSION_GROUP_UPDATE_MUTATION

    variables = {
        "id": graphene.Node.to_global_id("Group", group.id),
        "input": {"addPermissions": [AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name]},
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    permission_group_data = data["group"]

    group = Group.objects.get()
    assert group.name == old_group_name
    assert permission_group_data["name"] == group.name
    permissions = {
        permission["name"] for permission in permission_group_data["permissions"]
    }
    assert set(group.permissions.all().values_list("name", flat=True)) == permissions
    assert data["permissionGroupErrors"] == []


def test_permission_group_update_mutation_no_input_data(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    permission_manage_users,
    staff_api_client,
):
    """Ensure mutation doesn't change group when input is empty."""
    staff_user.user_permissions.add(permission_manage_staff, permission_manage_users)
    group = permission_group_manage_users
    query = PERMISSION_GROUP_UPDATE_MUTATION

    variables = {"id": graphene.Node.to_global_id("Group", group.id), "input": {}}
    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    errors = data["permissionGroupErrors"]
    permission_group_data = data["group"]

    assert errors == []
    assert permission_group_data["name"] == group.name
    permissions = {
        permission["name"] for permission in permission_group_data["permissions"]
    }
    assert set(group.permissions.all().values_list("name", flat=True)) == permissions


def test_permission_group_update_mutation_user_cannot_manage_group(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    staff_api_client,
    permission_manage_service_accounts,
):
    """Ensure that update mutation failed when user try to update group for which
    he doesn't have permission.
    """
    staff_user.user_permissions.add(permission_manage_service_accounts)
    group = permission_group_manage_users
    query = PERMISSION_GROUP_UPDATE_MUTATION

    variables = {
        "id": graphene.Node.to_global_id("Group", group.id),
        "input": {
            "name": "New permission group",
            "addPermissions": [AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name],
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    errors = data["permissionGroupErrors"]

    assert len(errors) == 1
    assert errors[0]["code"] == PermissionGroupErrorCode.OUT_OF_SCOPE_PERMISSION.name
    assert errors[0]["field"] is None


def test_permission_group_update_mutation_user_in_list_to_add_and_remove(
    permission_group_manage_users,
    staff_users,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
    permission_manage_service_accounts,
):
    """Ensure update mutation failed when user IDs are in both lists for adding
    and removing. Ensure mutation contains list of user IDs which cause
    the problem.
    """
    staff_user = staff_users[0]
    staff_user.user_permissions.add(
        permission_manage_users, permission_manage_service_accounts
    )
    group = permission_group_manage_users
    query = PERMISSION_GROUP_UPDATE_MUTATION

    staff_user2_id = graphene.Node.to_global_id("User", staff_users[1].pk)

    variables = {
        "id": graphene.Node.to_global_id("Group", group.id),
        "input": {
            "name": "New permission group",
            "addUsers": [
                graphene.Node.to_global_id("User", user.pk) for user in staff_users
            ],
            "removeUsers": [staff_user2_id],
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    errors = data["permissionGroupErrors"]

    assert len(errors) == 1
    assert errors[0]["code"] == PermissionGroupErrorCode.CANNOT_ADD_AND_REMOVE.name
    assert errors[0]["field"] is None
    assert errors[0]["permissions"] is None
    assert errors[0]["users"] == [staff_user2_id]


def test_permission_group_update_mutation_permissions_in_list_to_add_and_remove(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
    permission_manage_service_accounts,
    permission_manage_orders,
):
    """Ensure update mutation failed when permission items are in both lists for
    adding and removing. Ensure mutation contains list of permissions which cause
    the problem.
    """
    staff_user.user_permissions.add(
        permission_manage_users,
        permission_manage_service_accounts,
        permission_manage_orders,
    )
    group = permission_group_manage_users
    query = PERMISSION_GROUP_UPDATE_MUTATION

    permissions = [
        OrderPermissions.MANAGE_ORDERS.name,
        AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name,
    ]
    variables = {
        "id": graphene.Node.to_global_id("Group", group.id),
        "input": {
            "name": "New permission group",
            "addPermissions": permissions,
            "removePermissions": permissions,
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    errors = data["permissionGroupErrors"]

    assert len(errors) == 1
    assert errors[0]["code"] == PermissionGroupErrorCode.CANNOT_ADD_AND_REMOVE.name
    assert errors[0]["field"] is None
    assert set(errors[0]["permissions"]) == set(permissions)
    assert errors[0]["users"] is None


def test_permission_group_update_mutation_permissions_and_users_duplicated(
    permission_group_manage_users,
    staff_users,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
    permission_manage_service_accounts,
    permission_manage_orders,
):
    """Ensure updating mutations with the same permission and users in list for
    adding and removing failed. Mutation should failed. Error should contains list of
    users IDs and permissions that are duplicated.
    """
    staff_user = staff_users[0]
    staff_user.user_permissions.add(
        permission_manage_users,
        permission_manage_service_accounts,
        permission_manage_orders,
    )
    group = permission_group_manage_users
    query = PERMISSION_GROUP_UPDATE_MUTATION

    staff_user2_id = graphene.Node.to_global_id("User", staff_users[1].pk)

    permissions = [
        OrderPermissions.MANAGE_ORDERS.name,
        AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name,
    ]
    variables = {
        "id": graphene.Node.to_global_id("Group", group.id),
        "input": {
            "name": "New permission group",
            "addPermissions": permissions,
            "removePermissions": permissions,
            "addUsers": [
                graphene.Node.to_global_id("User", user.pk) for user in staff_users
            ],
            "removeUsers": [staff_user2_id],
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    errors = data["permissionGroupErrors"]

    assert len(errors) == 2
    assert {error["code"] for error in errors} == {
        PermissionGroupErrorCode.CANNOT_ADD_AND_REMOVE.name
    }
    assert {error["field"] for error in errors} == {None}
    assert set(permissions) in [
        set(error["permissions"]) if error["permissions"] else None for error in errors
    ]
    assert [staff_user2_id] in [error["users"] for error in errors]


def test_permission_group_update_mutation_user_add_customer_user(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
    permission_manage_service_accounts,
    customer_user,
):
    """Ensure update mutation with customer user in field for adding users failed.
    Ensure error contains list with user IDs which cause the problem.
    """
    staff_user.user_permissions.add(
        permission_manage_users, permission_manage_service_accounts
    )
    group = permission_group_manage_users
    query = PERMISSION_GROUP_UPDATE_MUTATION

    customer_user_id = graphene.Node.to_global_id("User", customer_user.pk)

    variables = {
        "id": graphene.Node.to_global_id("Group", group.id),
        "input": {
            "name": "New permission group",
            "addUsers": [
                graphene.Node.to_global_id("User", user.pk)
                for user in [staff_user, customer_user]
            ],
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    errors = data["permissionGroupErrors"]

    assert len(errors) == 1
    assert errors[0]["code"] == PermissionGroupErrorCode.ASSIGN_NON_STAFF_MEMBER.name
    assert errors[0]["field"] == "addUsers"
    assert errors[0]["permissions"] is None
    assert errors[0]["users"] == [customer_user_id]


def test_permission_group_update_mutation_lack_of_permission(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
    permission_manage_service_accounts,
    permission_manage_orders,
):
    """Ensure update mutation failed when user trying to add permission which
    he doesn't have.
    """
    staff_user.user_permissions.add(
        permission_manage_users, permission_manage_service_accounts
    )
    group = permission_group_manage_users
    query = PERMISSION_GROUP_UPDATE_MUTATION

    permissions = [
        OrderPermissions.MANAGE_ORDERS.name,
        AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name,
    ]
    variables = {
        "id": graphene.Node.to_global_id("Group", group.id),
        "input": {"name": "New permission group", "addPermissions": permissions},
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    errors = data["permissionGroupErrors"]

    assert len(errors) == 1
    assert errors[0]["code"] == PermissionGroupErrorCode.OUT_OF_SCOPE_PERMISSION.name
    assert errors[0]["field"] == "addPermissions"
    assert errors[0]["permissions"] == [OrderPermissions.MANAGE_ORDERS.name]
    assert errors[0]["users"] is None


def test_permission_group_update_mutation_multiply_errors(
    permission_group_manage_users,
    staff_user,
    customer_user,
    permission_manage_staff,
    staff_api_client,
    permission_manage_users,
    permission_manage_service_accounts,
    permission_manage_orders,
):
    """Ensure update mutation failed with all validation errors when input data
    is incorrent:
        - the same item in list for adding and removing (CANNOT_ADD_AND_REMOVE)
        - adding permission which user hasn't (OUT_OF_SCOPE_PERMISSION)
        - adding customer user (ASSIGN_NON_STAFF_MEMBER)
    """

    staff_user.user_permissions.add(
        permission_manage_service_accounts, permission_manage_users
    )
    group = permission_group_manage_users
    query = PERMISSION_GROUP_UPDATE_MUTATION

    user_ids = [
        graphene.Node.to_global_id("User", user.pk)
        for user in [staff_user, customer_user]
    ]
    permissions = [
        OrderPermissions.MANAGE_ORDERS.name,
        AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name,
    ]
    variables = {
        "id": graphene.Node.to_global_id("Group", group.id),
        "input": {
            "name": "New permission group",
            "addPermissions": permissions,
            "removePermissions": [AccountPermissions.MANAGE_SERVICE_ACCOUNTS.name],
            "addUsers": user_ids,
            "removeUsers": user_ids[:1],
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=(permission_manage_staff,)
    )
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupUpdate"]
    errors = data["permissionGroupErrors"]

    assert len(errors) == 4
    assert {error["field"] for error in errors} == {None, "addPermissions", "addUsers"}
    permission_errors = [error["permissions"] for error in errors]
    assert permissions[:1] in permission_errors
    assert permissions[1:] in permission_errors
    user_errors = [error["users"] for error in errors]
    assert user_ids[1:] in user_errors
    assert user_ids[:1] in user_errors
    assert {error["code"] for error in errors} == {
        PermissionGroupErrorCode.ASSIGN_NON_STAFF_MEMBER.name,
        PermissionGroupErrorCode.OUT_OF_SCOPE_PERMISSION.name,
        PermissionGroupErrorCode.CANNOT_ADD_AND_REMOVE.name,
    }
    assert data["group"] is None


PERMISSION_GROUP_DELETE_MUTATION = """
    mutation PermissionGroupDelete($id: ID!) {
        permissionGroupDelete(
            id: $id)
        {
            group{
                id
                name
                permissions {
                    name
                    code
                }
            }
            accountErrors{
                field
                code
                message
            }
        }
    }
    """


def test_group_delete_mutation(
    permission_group_manage_users, staff_user, permission_manage_staff, staff_api_client
):
    staff_user.user_permissions.add(permission_manage_staff)
    group = permission_group_manage_users
    group_name = group.name
    query = PERMISSION_GROUP_DELETE_MUTATION

    variables = {"id": graphene.Node.to_global_id("Group", group.id)}
    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["permissionGroupDelete"]
    errors = data["accountErrors"]
    permission_group_data = data["group"]

    assert errors == []
    assert permission_group_data["id"] == variables["id"]
    assert permission_group_data["name"] == group_name
    assert permission_group_data["permissions"] == []


QUERY_PERMISSION_GROUP_WITH_FILTER = """
    query ($filter: PermissionGroupFilterInput ){
        permissionGroups(first: 5, filter: $filter){
            edges{
                node{
                    id
                    name
                    permissions{
                        name
                        code
                    }
                    users {
                        email
                    }
                }
            }
        }
    }
    """


@pytest.mark.parametrize(
    "permission_group_filter, count",
    (({"search": "Manage user groups"}, 1), ({"search": "Manage"}, 2), ({}, 3)),
)
def test_permission_groups_query(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    staff_api_client,
    permission_group_filter,
    count,
):
    staff_user.user_permissions.add(permission_manage_staff)
    query = QUERY_PERMISSION_GROUP_WITH_FILTER

    Group.objects.bulk_create(
        [Group(name="Manage product."), Group(name="Remove product.")]
    )

    variables = {"filter": permission_group_filter}
    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["permissionGroups"]["edges"]

    assert len(data) == count


def test_permission_groups_no_permission_to_perform(
    permission_group_manage_users, permission_manage_staff, staff_api_client,
):
    query = QUERY_PERMISSION_GROUP_WITH_FILTER

    variables = {"filter": {"search": "Manage user groups"}}
    response = staff_api_client.post_graphql(query, variables)
    assert_no_permission(response)


QUERY_PERMISSION_GROUP_WITH_SORT = """
    query ($sort_by: PermissionGroupSortingInput!) {
        permissionGroups(first:5, sortBy: $sort_by) {
                edges{
                    node{
                        name
                    }
                }
            }
        }
"""


@pytest.mark.parametrize(
    "permission_group_sort, result",
    (
        (
            {"field": "NAME", "direction": "ASC"},
            ["Add", "Manage user groups.", "Remove"],
        ),
        (
            {"field": "NAME", "direction": "DESC"},
            ["Remove", "Manage user groups.", "Add"],
        ),
    ),
)
def test_permission_group_with_sort(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    staff_api_client,
    permission_group_sort,
    result,
):
    staff_user.user_permissions.add(permission_manage_staff)
    query = QUERY_PERMISSION_GROUP_WITH_SORT

    Group.objects.bulk_create([Group(name="Add"), Group(name="Remove")])

    variables = {"sort_by": permission_group_sort}
    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["permissionGroups"]["edges"]

    for order, group_name in enumerate(result):
        assert data[order]["node"]["name"] == group_name


QUERY_PERMISSION_GROUP = """
    query ($id: ID! ){
        permissionGroup(id: $id){
            id
            name
            permissions {
                name
                code
            }
            users{
                email
            }
        }
    }
    """


def test_permission_group_query(
    permission_group_manage_users,
    staff_user,
    permission_manage_staff,
    staff_api_client,
):
    staff_user.user_permissions.add(permission_manage_staff)
    group = permission_group_manage_users
    query = QUERY_PERMISSION_GROUP

    group_staff_user = group.user_set.first()

    variables = {"id": graphene.Node.to_global_id("Group", group.id)}
    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["permissionGroup"]

    assert data["name"] == group.name
    assert len(data["users"]) == 1
    assert data["users"][0]["email"] == group_staff_user.email
    result_permissions = {permission["name"] for permission in data["permissions"]}
    assert (
        set(group.permissions.all().values_list("name", flat=True))
        == result_permissions
    )
    permissions_codes = {
        permission["code"].lower() for permission in data["permissions"]
    }
    assert (
        set(group.permissions.all().values_list("codename", flat=True))
        == permissions_codes
    )


def test_permission_group_no_permission_to_perform(
    permission_group_manage_users, permission_manage_staff, staff_api_client,
):
    group = permission_group_manage_users
    query = QUERY_PERMISSION_GROUP

    variables = {"id": graphene.Node.to_global_id("Group", group.id)}
    response = staff_api_client.post_graphql(query, variables)
    assert_no_permission(response)
