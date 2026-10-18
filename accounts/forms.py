from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from social.utils import clean_phone_number

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ("email", "phone_number", "first_name", "last_name", "password1", "password2")

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number")
        if phone:
            return clean_phone_number(phone)
        return phone

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="ایمیل")

User = get_user_model()


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        label="ایمیل",
        required=True,
        widget=forms.EmailInput(attrs={
            "class": "form-input",
            "placeholder": "ایمیل حساب کاربری",
            "autocomplete": "email",
            "dir": "ltr",
        })
    )


class ResetPasswordForm(forms.Form):
    password1 = forms.CharField(
        label="رمز عبور جدید",
        required=True,
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "placeholder": "رمز عبور جدید",
            "autocomplete": "new-password",
            "dir": "ltr",
        })
    )
    password2 = forms.CharField(
        label="تکرار رمز عبور",
        required=True,
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "placeholder": "تکرار رمز عبور",
            "autocomplete": "new-password",
            "dir": "ltr",
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError(
                    "رمزهای عبور وارد شده یکسان نیستند."
                )
            validate_password(password1)
        return cleaned_data