import random
import re
import time
from datetime import timedelta

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import (
    url_has_allowed_host_and_scheme,
    urlsafe_base64_decode,
    urlsafe_base64_encode,
)

from social.models import SiteSettings
from social.utils import SendOTP

from .forms import (
    CustomAuthenticationForm,
    CustomUserCreationForm,
    ForgotPasswordForm,
    ResetPasswordForm,
)
from .models import CustomUser, PhoneOTP
from .validators import validate_iran_phone

User = get_user_model()


def normalize_iran_phone(phone):
    if not phone:
        return ""
    p = str(phone).strip()
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    for i, d in enumerate(persian_digits):
        p = p.replace(d, str(i))
    for i, d in enumerate(arabic_digits):
        p = p.replace(d, str(i))
    p = re.sub(r"[^\d+]", "", p)
    if p.startswith("+98"):
        p = "0" + p[3:]
    elif p.startswith("0098"):
        p = "0" + p[4:]
    elif p.startswith("98") and len(p) == 12:
        p = "0" + p[2:]
    elif p.startswith("9") and len(p) == 10:
        p = "0" + p
    return p


def _login_page(request, error="", active_tab="login"):
    return render(
        request,
        "login.html",
        {
            "settings": SiteSettings.objects.first(),
            "current_time": int(time.time()),
            "error": error,
            "active_tab": active_tab,
        },
    )


def register_view(request):
    settings = SiteSettings.objects.first()
    current_time = int(time.time())
    if request.method != "POST":
        return _login_page(request, active_tab="register")

    form = CustomUserCreationForm(request.POST)
    if not form.is_valid():
        err_msg = "اطلاعات وارد شده صحیح نیست."
        for field, errors in form.errors.items():
            if errors:
                err_msg = errors[0]
                break
        return _login_page(request, err_msg, active_tab="register")

    raw_phone = form.cleaned_data["phone_number"]
    phone = normalize_iran_phone(raw_phone)
    email = form.cleaned_data["email"].strip().lower()

    if not validate_iran_phone(phone):
        return _login_page(request, "شماره موبایل وارد شده معتبر نیست (مثال: 09123456789).", active_tab="register")

    if CustomUser.objects.filter(phone_number=phone).exists():
        return _login_page(request, "این شماره موبایل قبلاً در سایت ثبت‌نام کرده است. لطفاً وارد شوید.", active_tab="login")

    if CustomUser.objects.filter(email__iexact=email).exists():
        return _login_page(request, "این ایمیل قبلاً در سایت ثبت‌نام کرده است. لطفاً وارد شوید.", active_tab="login")

    # PhoneOTP lookup
    otp = PhoneOTP.objects.filter(phone_number=phone).first()
    if otp:
        # Reset any past block if present
        if otp.blocked_until:
            otp.blocked_until = None
            otp.save(update_fields=["blocked_until"])

        if not otp.can_send():
            return render(request, "verify-otp.html", {
                "phone": phone,
                "error": "کد تأیید به تازگی برای شما ارسال شده است. لطفاً آن را وارد نمایید.",
                "settings": settings,
                "current_time": current_time
            })


    code = str(random.randint(100000, 999999))
    SendOTP(phone, code)

    if otp is None:
        otp = PhoneOTP(phone_number=phone)

    otp.code = make_password(code)
    otp.first_name = form.cleaned_data["first_name"]
    otp.last_name = form.cleaned_data["last_name"]
    otp.email = email
    otp.password = make_password(form.cleaned_data["password1"])
    otp.created_at = timezone.now()
    otp.updated_at = timezone.now()
    otp.attempts = 0
    otp.send_count = (otp.send_count + 1) if otp.id else 1
    otp.save()

    return render(request, "verify-otp.html", {
        "phone": phone,
        "error": "",
        "settings": settings,
        "current_time": current_time
    })


def verify_otp_view(request):
    settings = SiteSettings.objects.first()
    current_time = int(time.time())
    if request.method != "POST":
        return redirect("login")

    phone = normalize_iran_phone(request.POST.get("phone", ""))
    code = str(request.POST.get("code", "")).strip()

    if not phone or not code:
        return render(request, "verify-otp.html", {
            "phone": phone,
            "error": "لطفاً کد تأیید ۶ رقمی را وارد کنید.",
            "settings": settings,
            "current_time": current_time
        })

    otp = PhoneOTP.objects.filter(phone_number=phone).first()
    if otp is None:
        return _login_page(request, "اطلاعات ثبت‌نام یافت نشد یا منقضی شده است. لطفاً مجدداً ثبت‌نام کنید.", active_tab="register")

    # Reset any past block if present
    if otp.blocked_until:
        otp.blocked_until = None
        otp.save(update_fields=["blocked_until"])

    if otp.is_expired():
        return render(request, "verify-otp.html", {
            "phone": phone,
            "error": "کد تأیید منقضی شده است. لطفاً روی ارسال مجدد کد کلیک کنید.",
            "settings": settings,
            "current_time": current_time
        })

    if not check_password(code, otp.code):
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        return render(request, "verify-otp.html", {
            "phone": phone,
            "error": "کد وارد شده اشتباه است. لطفاً مجدداً بررسی و وارد کنید.",
            "settings": settings,
            "current_time": current_time
        })

    # Code is valid! Create user or get existing
    user = CustomUser.objects.filter(phone_number=otp.phone_number).first()
    if not user:
        user = CustomUser.objects.create(
            email=otp.email,
            phone_number=otp.phone_number,
            first_name=otp.first_name,
            last_name=otp.last_name,
            password=otp.password,
            is_active=True
        )
    else:
        user.first_name = otp.first_name or user.first_name
        user.last_name = otp.last_name or user.last_name
        user.password = otp.password
        user.is_active = True
        user.save()

    otp.delete()
    login(request, user)
    return redirect("/")


def resend_otp_view(request):
    settings = SiteSettings.objects.first()
    current_time = int(time.time())
    raw_phone = request.GET.get("phone_number") or request.GET.get("phone") or request.POST.get("phone") or ""
    phone = normalize_iran_phone(raw_phone)

    if not phone:
        return redirect("login")

    otp = PhoneOTP.objects.filter(phone_number=phone).first()
    if otp is None:
        return _login_page(request, "اطلاعات ثبت‌نام یافت نشد. لطفاً مجدداً اقدام به ثبت‌نام نمایید.", active_tab="register")

    # Reset any past block if present
    if otp.blocked_until:
        otp.blocked_until = None
        otp.save(update_fields=["blocked_until"])

    if not otp.can_send():
        return render(request, "verify-otp.html", {
            "phone": phone,
            "error": "ارسال مجدد پیامک فقط هر ۶۰ ثانیه یک‌بار امکان‌پذیر است.",
            "settings": settings,
            "current_time": current_time
        })


    code = str(random.randint(100000, 999999))
    SendOTP(phone, code)

    otp.code = make_password(code)
    otp.created_at = timezone.now()
    otp.updated_at = timezone.now()
    otp.attempts = 0
    otp.send_count += 1
    otp.save()

    return render(request, "verify-otp.html", {
        "phone": phone,
        "error": "",
        "success": "کد تأیید جدید با موفقیت پیامک شد.",
        "settings": settings,
        "current_time": current_time
    })


def login_view(request):
    if request.method == "POST":
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            next_url = request.GET.get("next") or request.POST.get("next")
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("/")
        return _login_page(request, "ایمیل یا رمز عبور اشتباه است.", active_tab="login")
    return _login_page(request, active_tab="login")


def logout_view(request):
    logout(request)
    return redirect("login")


class PasswordResetTokenGeneratorCustom(PasswordResetTokenGenerator):
    pass


password_reset_generator = PasswordResetTokenGeneratorCustom()


def forgot_password_view(request):
    if request.method == "POST":
        form = ForgotPasswordForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()

            try:
                user = User.objects.get(email__iexact=email, is_active=True)
            except User.DoesNotExist:
                user = None

            if user:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = password_reset_generator.make_token(user)
                reset_hash = f"{uid}:{token}"

                reset_url = (
                    request.build_absolute_uri(reverse("reset_password"))
                    + f"?hash={reset_hash}"
                )

                subject = "بازیابی رمز عبور حساب کاربری"
                message = f"""
سلام {user.first_name or 'کاربر عزیز'}

درخواستی برای تغییر رمز عبور حساب شما در سایت ثبت شده است.

برای تعیین رمز عبور جدید روی لینک زیر کلیک کنید:

{reset_url}

اگر این درخواست توسط شما ارسال نشده است، این ایمیل را نادیده بگیرید.

این لینک پس از مدت محدودی منقضی خواهد شد.

با احترام
تیم پشتیبانی
"""

                try:
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=django_settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=False,
                    )
                except Exception:
                    return render(
                        request,
                        "resetpassword.html",
                        {
                            "error": "ارسال ایمیل با مشکل مواجه شد. لطفاً بعداً دوباره تلاش کنید.",
                            "form": form,
                            "current_time": int(time.time()),
                        },
                    )

            # چه کاربر وجود داشته باشد چه نداشته باشد، پیام یکسان نمایش داده می‌شود
            return render(
                request,
                "resetpassword.html",
                {
                    "form": ForgotPasswordForm(),
                    "success": "اگر حسابی با این ایمیل وجود داشته باشد، لینک بازیابی رمز عبور برای شما ارسال خواهد شد.",
                    "current_time": int(time.time()),
                },
            )
    else:
        form = ForgotPasswordForm()

    return render(
        request,
        "resetpassword.html",
        {"form": form, "current_time": int(time.time())},
    )


def reset_password_view(request):
    reset_hash = request.GET.get("hash", "").strip()
    if not reset_hash:
        return redirect("forgot_password")

    try:
        uid, token = reset_hash.split(":", 1)
    except ValueError:
        return redirect("forgot_password")

    try:
        user_id = urlsafe_base64_decode(uid).decode()
        user = User.objects.get(pk=user_id, is_active=True)
    except (ValueError, TypeError, OverflowError, User.DoesNotExist):
        return redirect("forgot_password")

    if not password_reset_generator.check_token(user, token):
        return redirect("forgot_password")

    if request.method == "POST":
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data["password1"])
            user.save(update_fields=["password"])
            return redirect("login")
    else:
        form = ResetPasswordForm()

    return render(
        request,
        "reset_password.html",
        {
            "form": form,
            "reset_hash": reset_hash,
            "current_time": int(time.time()),
        },
    )

