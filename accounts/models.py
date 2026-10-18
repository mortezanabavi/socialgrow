from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import uuid, jdatetime
from django.conf import settings
from django.utils.crypto import get_random_string
import requests
from django.utils import timezone
from datetime import timedelta


def my_function():
    from social.models import SiteSettings
    site = SiteSettings.objects.first()
    return site

class CustomUserManager(BaseUserManager):
    def create_user(self, email, phone_number, password=None, **extra_fields):
        if not email:
            raise ValueError("ایمیل باید وارد شود")
        if not phone_number:
            raise ValueError("شماره تلفن باید وارد شود")
        
        from social.utils import clean_phone_number
        phone_number = clean_phone_number(phone_number)
        email = self.normalize_email(email)
        user = self.model(email=email, phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, phone_number, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, verbose_name="ایمیل")
    phone_number = models.CharField(max_length=15, unique=True, verbose_name="شماره تلفن")
    first_name = models.CharField(max_length=100, blank=True, verbose_name="نام")
    last_name = models.CharField(max_length=100, blank=True, verbose_name="نام خانوادگی")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, verbose_name="موجودی")
    last_orders = models.JSONField(default=list, blank=True, verbose_name="اخرین سفارش")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    is_staff = models.BooleanField(default=False, verbose_name="ادمین")
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ عضویت")
    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phone_number']
    
    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if self.phone_number:
            from social.utils import clean_phone_number
            self.phone_number = clean_phone_number(self.phone_number)
        super().save(*args, **kwargs)

    def send_balance_charge_sms(self):
        if self.phone_number:
            try:
                from social.utils import send_wallet_charge_sms
                return send_wallet_charge_sms(phone=self.phone_number, price=int(self.balance))
            except Exception as e:
                print(f"Error in send_balance_charge_sms: {e}")
        return False
        
class PhoneOTP(models.Model):
    phone_number = models.CharField(max_length=13, unique=True)
    code = models.CharField(max_length=128)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    password = models.CharField(max_length=255)
    attempts = models.PositiveSmallIntegerField(default=0)
    send_count = models.PositiveSmallIntegerField(default=1)
    blocked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=2)

    def can_send(self):
        return timezone.now() > self.updated_at + timedelta(seconds=60)

    def is_blocked(self):
        if self.blocked_until:
            return timezone.now() < self.blocked_until
        return False
        
    def remaining_block_time(self):
        if self.is_blocked():
            return self.blocked_until - timezone.now()
        return None

    def save(self, *args, **kwargs):
        from social.utils import clean_phone_number, to_english_digits
        if self.phone_number:
            self.phone_number = clean_phone_number(self.phone_number)
        if self.code:
            self.code = to_english_digits(str(self.code)).strip()
        super().save(*args, **kwargs)
       
class IncreaseTransaction(models.Model):
    class Status(models.TextChoices):
        PENDINGP = "pendingPayment", "در انتظار پرداخت"
        PENDINGC = "pendingConfirm", "در انتظار تایید"
        SUCCESS = "success", "موفق"
        FAILED = "failed", "ناموفق"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions", verbose_name="کاربر")
    amount = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="مبلغ شارژ")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان شارژ")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDINGP, verbose_name="وضعیت")
    tracking_code = models.CharField(max_length=64, unique=True, editable=False, verbose_name="کد پیگیری")

    class Meta:
        verbose_name = "افزایش موجودی"
        verbose_name_plural = "افزایش موجودی ها"

    def save(self, *args, **kwargs):
        if not self.tracking_code:
            self.tracking_code = uuid.uuid4().hex.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.amount} - {self.status}"

class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "Open", "باز"
        ANSWERED = "Answered", "پاسخ داده شده"
        REVIEW = "Review", "درحال بررسی"
        CLOSED = "Closed", "بسته شده"

    class Priority(models.TextChoices):
        LOW = "Low", "کم"
        NORMAL = "Normal", "عادی"
        HIGH = "High", "زیاد"
        URGENT = "Urgent", "فوری"

    class Department(models.TextChoices):
        SUPPORT = "Support", "پشتیبانی"
        FINANCIAL = "Financial", "مالی"
        TECHNICAL = "Technical", "فنی"
        SALES = "Sales", "فروش"
        OTHER = "Other", "سایر"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets", verbose_name="کاربر")
    title = models.CharField(max_length=255, verbose_name="عنوان تیکت")
    department = models.CharField(max_length=20, choices=Department.choices, default=Department.SUPPORT, verbose_name="بخش")
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL, verbose_name="اولویت")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, verbose_name="وضعیت")
    tracking_code = models.CharField(max_length=64, unique=True, editable=False, verbose_name="کد پیگیری")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین بروزرسانی")
    closed_at = models.DateTimeField(null=True,blank=True, verbose_name="زمان بسته شدن")
    is_read_by_admin = models.BooleanField(default=False, verbose_name="خوانده شده توسط ادمین")
    is_read_by_user = models.BooleanField(default=True, verbose_name="خوانده شده توسط کاربر")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "تیکت"
        verbose_name_plural = "تیکت‌ها"
        
    def get_lastup_date(self):
        from django.utils import timezone
        if self.updated_at:
            local_time = timezone.localtime(self.updated_at)
            j_date = jdatetime.datetime.fromgregorian(datetime=local_time)
            return j_date.strftime("%Y/%m/%d - %H:%M")
        return ""
        
    def get_create_date(self):
        from django.utils import timezone
        if self.created_at:
            local_time = timezone.localtime(self.created_at)
            j_date = jdatetime.datetime.fromgregorian(datetime=local_time)
            return j_date.strftime("%Y/%m/%d - %H:%M")
        return ""
        
    def get_close_date(self):
        from django.utils import timezone
        if self.closed_at:
            local_time = timezone.localtime(self.closed_at)
            j_date = jdatetime.datetime.fromgregorian(datetime=local_time)
            return j_date.strftime("%Y/%m/%d - %H:%M")
        return ""

    def save(self, *args, **kwargs):
        if not self.tracking_code:
            self.tracking_code = uuid.uuid4().hex[:12].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} | {self.user}"
        
    def get_status(self):
        return self.status.lower().replace('closed', 'بسته').replace('open', 'باز').replace('review', 'درحال بررسی').replace('answered', 'پاسخ داده شده')
        
class TicketMessage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages", verbose_name="تیکت")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="ارسال کننده")
    message = models.TextField(verbose_name="متن پیام")
    attachment = models.FileField(upload_to="tickets/", blank=True, null=True, verbose_name="فایل پیوست")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ارسال")

    class Meta:
        ordering = ["created_at"]
        verbose_name = "پیام تیکت"
        verbose_name_plural = "پیام‌های تیکت"
        
    def get_message_date(self):
        from django.utils import timezone
        if self.created_at:
            local_time = timezone.localtime(self.created_at)
            j_date = jdatetime.datetime.fromgregorian(datetime=local_time)
            return j_date.strftime("%Y/%m/%d - %H:%M")
        return ""

    def __str__(self):
        return f"{self.ticket.tracking_code}"
        
class UserPayment(models.Model):
    class PaymentType(models.TextChoices):
        TRX = "Trx", "ترون"
        ZIBAL = "Zibal", "زیبال"
        SIZPAY = "Sizpay", "سیزپی"
        CARD = "Card", "کارت به کارت"
        
    class PaymentStatus(models.TextChoices):
        PAYMENT = "PAYMENT", "اماده پرداخت"
        FINISHED = "Finished", "پرداخت شده"
        
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="walletuser", verbose_name="کاربر")
    payment = models.CharField(max_length=20, choices=PaymentType.choices, default=PaymentType.ZIBAL, verbose_name="نوع پرداخت")
    authority = models.CharField(max_length=100, verbose_name="کد پرداخت", default="notset")
    amount = models.BigIntegerField(default=0, verbose_name="مبلغ")
    wallet_address = models.CharField(max_length=500, verbose_name="آدرس کیف پول", default="notset")
    public_key = models.CharField(max_length=500, verbose_name="پابلیک کی", default="notset")
    private_key = models.CharField(max_length=500, verbose_name="پرایوت کی", default="notset")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ساخت")
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PAYMENT, verbose_name="وضعیت")
    
    def save(self, *args, **kwargs):
        if self.authority:
            from social.utils import to_english_digits
            self.authority = to_english_digits(str(self.authority)).strip()
        super().save(*args, **kwargs)
    
    def generate_payment(self):
        if self.payment == UserPayment.PaymentType.TRX:
            from social.utils import generate_trx_wallet
            self.wallet_address, self.private_key, self.public_key = generate_trx_wallet()
            self.save(update_fields=["wallet_address", "private_key", "public_key",])
            return True
        elif self.payment == UserPayment.PaymentType.SIZPAY:
            site_settings = my_function()
            domain = site_settings.domain if (site_settings and site_settings.domain) else "localhost:8000"
            scheme = "http" if ("localhost" in domain or "127.0.0.1" in domain) else "https"
            callback_uri = f"{scheme}://{domain}/verify"
            import time, json
            data = {
                "sizPayKey": site_settings.sizpay_merchant_id if site_settings else getattr(settings, 'SIZPAY_MERCHANT', ''),
                "ReturnURL": callback_uri,
                "Amount": self.amount * 10,
                "OrderID": int(time.time()),
                "InvoiceNo": str(self.id),
                "DocDate": "",
                "ExtraInf": f"شارژ کیف پول - شناسه {self.id}",
                "AppExtraInf": {
                    "PayerNm": f"{self.user.first_name} {self.user.last_name}".strip(),
                    "PayerMobile": self.user.phone_number,
                    "PayerEmail": self.user.email,
                    "Descr": f"شارژ کیف پول - شناسه {self.id}",
                    "PayTitleID": 0
                }
            }
            json_data = json.dumps(data)
            headers = {
                'Content-Type': 'application/json',
                'Content-Length': str(len(json_data)),
                'User-Agent': 'Sizpay Rest Api v1'
            }
            try:
                response = requests.post(
                    'https://rt.sizpay.ir/api/PaymentSimple/GetTokenSimple',
                    data=json_data,
                    headers=headers,
                    timeout=15
                )
                if response.status_code == 200:
                    result = response.json()
                    if str(result.get('ResCod')) in ('0', '00'):
                        self.authority = result.get('Token')
                        self.save()
                        return True
                return False
            except Exception:
                return False
        else:
            url = f"https://gateway.zibal.ir/v1/request"
            site_settings = my_function()
            domain = site_settings.domain if (site_settings and site_settings.domain) else "localhost:8000"
            scheme = "http" if ("localhost" in domain or "127.0.0.1" in domain) else "https"
            callback_uri = f"{scheme}://{domain}/verify"
            merchant_id = site_settings.zibal_merchant_id if (site_settings and site_settings.zibal_merchant_id not in ['notset', '', None]) else getattr(settings, 'ZIBAL_MERCHANT', 'zibal')
            parameters = {
                "merchant": merchant_id,
                "callbackUrl": callback_uri,
                "orderId": f"WAL-{self.id}",
                "description": f"شارژ کیف پول کاربری - شناسه {self.id}",
                "amount": self.amount * 10
            }
            headers = {
                "Content-Type": "application/json"
            }
            try:
                response = requests.post(
                    url,
                    json=parameters,
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                res_data = response.json()
                if res_data.get('result') == 100:
                    self.authority = str(res_data['trackId'])
                    self.save()
                    return True
                return False
            except requests.exceptions.Timeout:
                return False
            except requests.exceptions.ConnectionError:
                return False
            except Exception:
                return False
        
    def confirm_payment(self):
        stsetting = my_function()
        from social.utils import get_trx_balance, get_trx_price, transfer_balance
        balance = get_trx_balance(self.wallet_address)
        b = int(balance)/1000000
        rial = int(get_trx_price() * (b))
        if rial >= self.amount:
            transfer_balance(self.wallet_address, self.private_key, stsetting.tron_wallet_address)
            return True
        return False
    
    class Meta:
        verbose_name = "شارژحساب"
        verbose_name_plural = "شارژ حساب ها"
    
    def __str__(self):
        return "پرداخت کاربر"
