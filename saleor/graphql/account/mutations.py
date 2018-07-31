import graphene
from django.contrib.auth.tokens import default_token_generator

from ...account import models
from ...core.permissions import MODELS_PERMISSIONS, get_permissions
from ..core.mutations import BaseMutation, ModelDeleteMutation, ModelMutation
from ..order.mutations.draft_orders import AddressInput
from ..utils import get_node


class UserInput(graphene.InputObjectType):
    email = graphene.String(
        description='The unique email address of the user.')
    note = graphene.String(description='A note about the user.')


class StaffInput(UserInput):
    permissions = graphene.List(
        graphene.String,
        description='List of permission code names to assign to this user.')


class CustomerCreate(ModelMutation):
    class Arguments:
        input = UserInput(
            description='Fields required to create a customer.', required=True)

    class Meta:
        description = 'Creates a new customer.'
        exclude = ['password']
        model = models.User

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('account.manage_users')


class CustomerUpdate(CustomerCreate):
    class Arguments:
        id = graphene.ID(
            description='ID of a customer to update.', required=True)
        input = UserInput(
            description='Fields required to update a customer.', required=True)

    class Meta:
        description = 'Updates an existing customer.'
        exclude = ['password']
        model = models.User


class StaffCreate(ModelMutation):
    class Arguments:
        input = StaffInput(
            description='Fields required to create a staff user.',
            required=True)

    class Meta:
        description = 'Creates a new staff user.'
        exclude = ['password']
        model = models.User

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.is_staff

    @classmethod
    def clean_input(cls, info, instance, input, errors):
        cleaned_input = super().clean_input(info, instance, input, errors)

        # set is_staff to True to create a staff user
        cleaned_input['is_staff'] = True

        # clean and prepare permissions
        if 'permissions' in cleaned_input:
            permissions = cleaned_input['permissions']
            cleaned_permissions = []
            for code in permissions:
                if code not in MODELS_PERMISSIONS:
                    error_msg = 'Unknown permission: %s' % code
                    cls.add_error(errors, 'permissions', error_msg)
                else:
                    cleaned_permissions.append(code)
            if not errors:
                permission_objs = get_permissions(cleaned_permissions)
                cleaned_input['user_permissions'] = permission_objs
        return cleaned_input


class StaffUpdate(StaffCreate):
    class Arguments:
        id = graphene.ID(
            description='ID of a staff user to update.', required=True)
        input = StaffInput(
            description='Fields required to update a staff user.',
            required=True)

    class Meta:
        description = 'Updates an existing staff user.'
        exclude = ['password']
        model = models.User


class SetPasswordInput(graphene.InputObjectType):
    token = graphene.String(
        description='A one-time token required to set the password.',
        required=True)
    password = graphene.String(description='Password', required=True)


class SetPassword(ModelMutation):
    INVALID_TOKEN = 'Invalid or expired token.'

    class Arguments:
        id = graphene.ID(
            description='ID of a user to set password whom.', required=True)
        input = SetPasswordInput(
            description='Fields required to set password.', required=True)

    class Meta:
        description = 'Sets user password.'
        model = models.User

    @classmethod
    def clean_input(cls, info, instance, input, errors):
        cleaned_input = super().clean_input(info, instance, input, errors)
        token = cleaned_input.pop('token')
        if not default_token_generator.check_token(instance, token):
            cls.add_error(errors, 'token', SetPassword.INVALID_TOKEN)
        return cleaned_input

    @classmethod
    def save(cls, info, instance, cleaned_input):
        instance.set_password(cleaned_input['password'])
        instance.save()


class AddressCreateInput(AddressInput):
    user_id = graphene.ID(
        description='ID of a user to create address for', required=True)


class AddressCreate(ModelMutation):
    class Arguments:
        input = AddressCreateInput(
            description='Fields required to create address', required=True)

    class Meta:
        description = 'Creates user address'
        model = models.Address

    @classmethod
    def clean_input(cls, info, instance, input, errors):
        user_id = input.get('user_id')
        user = get_node(info, user_id)
        cleaned_input = super().clean_input(info, instance, input, errors)
        cleaned_input['user'] = user
        return cleaned_input

    @classmethod
    def save(cls, info, instance, cleaned_input):
        super().save(info, instance, cleaned_input)
        user = cleaned_input.get('user')
        if user:
            instance.user_addresses.add(user)
            instance.save()

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('account.edit_user')


class AddressUpdate(ModelMutation):
    class Arguments:
        id = graphene.ID(
            description='ID of address to update', required=True)
        input = AddressInput(
            description='Fields required to update address', required=True)

    class Meta:
        description = 'Updates address'
        model = models.Address
        exclude = ['user_addresses']

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('account.edit_user')


class AddressDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of address to delete.')

    class Meta:
        description = 'Deletes an address'
        model = models.Address

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('account.edit_user')
