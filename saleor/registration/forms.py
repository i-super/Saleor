from django import forms
from django.contrib.auth import forms as django_forms
from django.core.urlresolvers import reverse
from django.http.request import HttpRequest
from django.utils.translation import pgettext

from templated_email import send_templated_mail

from saleor.userprofile.models import User


class LoginForm(django_forms.AuthenticationForm):
    username = forms.EmailField(
        label=pgettext('Form field', 'Email'), max_length=75)

    def __init__(self, request=None, *args, **kwargs):
        super(LoginForm, self).__init__(request=request, *args, **kwargs)
        if request:
            email = request.GET.get('email')
            if email:
                self.fields['username'].initial = email


class SignupForm(forms.ModelForm):
    password = forms.CharField(
        label=pgettext('User form field', 'Password'),
        widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('email',)

    def __init__(self, *args, **kwargs):
        super(SignupForm, self).__init__(*args, **kwargs)
        if self._meta.model.USERNAME_FIELD in self.fields:
            self.fields[self._meta.model.USERNAME_FIELD].widget.attrs.update(
                {'autofocus': ''})

    def save(self, request=None, commit=True):
        user = super(SignupForm, self).save(commit=False)
        password = self.cleaned_data['password']
        user.set_password(password)
        if commit:
            user.save()
        return user


class PasswordSetUpForm(django_forms.PasswordResetForm):
    """
        PasswordSetUpForm that overrides sending emails to use templated email.
        Allows setting password for new users that have no usable password.
    """

    def get_users(self, email):
        active_users = User.objects.filter(email__iexact=email, is_active=True)
        return active_users

    def send_mail(
            self, subject_template_name, email_template_name, context,
            from_email, to_email, html_email_template_name=None):
        reset_url = HttpRequest.build_absolute_uri(
            reverse(
                'account_reset_password_confirm',
                kwargs={'uidb64': context['uid'], 'token': context['token']}))
        context['reset_url'] = reset_url
        send_templated_mail(
            'account/password_set', from_email=from_email,
            recipient_list=[to_email], context=context)
