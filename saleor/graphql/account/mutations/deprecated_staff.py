import graphene
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from ....account import emails, models
from ....account.error_codes import AccountErrorCode
from ...core.mutations import BaseMutation


def send_user_password_reset_email(user, site):
    context = {
        "email": user.email,
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
        "site_name": site.name,
        "domain": site.domain,
        "protocol": "https" if settings.ENABLE_SSL else "http",
    }
    emails.send_user_password_reset_email(user.email, context, user.pk)


class PasswordReset(BaseMutation):
    class Arguments:
        email = graphene.String(description="Email.", required=True)

    class Meta:
        description = (
            "DEPRECATED: Will be removed in Saleor 2.10, use RequestPasswordReset "
            "instead. Sends an email with the account password change link to customer."
        )
        permissions = ("account.manage_users",)

    @classmethod
    def perform_mutation(cls, _root, info, email):
        try:
            user = models.User.objects.get(email=email)
        except ObjectDoesNotExist:
            raise ValidationError(
                {
                    "email": ValidationError(
                        "User with this email doesn't exist",
                        code=AccountErrorCode.NOT_FOUND,
                    )
                }
            )
        site = info.context.site
        send_user_password_reset_email(user, site)
        return PasswordReset()
