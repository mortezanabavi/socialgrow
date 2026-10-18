from django.db import models
from django.utils.crypto import get_random_string
from django.conf import settings
from accounts.models import IncreaseTransaction, Ticket, TicketMessage, CustomUser
import requests, json, jdatetime, time, random, string
import math
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils import timezone

class Product(models.Model):
    APP_CHOICES = (
        ("0", "فیسبوک"),
        ("1", "تلگرام"),
        ("2", "اینستاگرام"),
        ("3", "یوتیوب"),
        ("4", "ایکس ، توییتر"),
        ("5", "تیک تاک"),
        ("6", "اسپاتیفای"),
        ("7", "لینکدین"),
        ("8", "دیسکورد"),
        ("9", "ترافیک سایت"),
        ("10", "بسته اینترنت"),
        ("11", "شارژ سیم کارت"),
    )
    is_available = models.BooleanField(default=True,
        verbose_name="موجود است؟"
    )
    uni_code = models.PositiveBigIntegerField(default=0,
        unique=True, verbose_name="کد عددی محصول")
    name = models.CharField(max_length=99,
        verbose_name="نام محصول")
    exact_count = models.IntegerField(
        verbose_name="تعداد دقیق", default=0)
    slug = models.SlugField(max_length=120,
        unique=True, allow_unicode=True, verbose_name="اسلاگ")
    meta_description = models.TextField(
        verbose_name="توضیحات متا", default="بدون توضیح")
    service_id = models.PositiveBigIntegerField(
        verbose_name="آیدی سرویس")
    en = models.CharField(max_length=99, 
        verbose_name="برنامه هدف انگلیسی", default="telegram")
    app = models.CharField(
        max_length=2, choices=APP_CHOICES,
        verbose_name="برنامه هدف")
    cover_image = models.ImageField(
        upload_to="products/covers/", null=True, blank=True,
        verbose_name="تصویر کاور محصول")
    description = models.TextField(
        verbose_name="توضیحات محصول", null=True, blank=True)
    price = models.DecimalField(
        verbose_name="قیمت محصول (1000 عدد) به دلار", max_digits=10, decimal_places=5)
    min_order = models.PositiveBigIntegerField(
        verbose_name="حداقل سفارش", default=100)
    max_order = models.PositiveBigIntegerField(
        verbose_name="حداکثر سفارش", default=1000)
    discount = models.PositiveBigIntegerField(
        verbose_name="تخفیف محصول", default=0)
    selled_count = models.IntegerField(
        verbose_name="تعداد فروش", default=0)
    sub_products = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='parent_products',
        verbose_name="محصولات زیرمجموعه / پکیج‌های متغیر"
    )
        
    def round_price(self, n):
        if n < 1000:
            return math.ceil(n / 50) * 50
        elif n < 10000:
            return math.ceil(n / 500) * 500
        else:
            return math.ceil(n / 5000) * 5000
    
    def toman_price(self):
        from .utils import get_usdt_price
        base_price = self.price * get_usdt_price()
        try:
            site_settings = SiteSettings.objects.first()
            commission_percent = float(site_settings.commission_percent if site_settings else 20)
        except:
            commission_percent = 20
        base_price = int(base_price) * float(1 + commission_percent / 100)
        return self.round_price(int(base_price))
        
    def rial_price(self):
        return int(self.toman_price() * 10)
        
    def per_price(self):
        return int(self.toman_price() / 1000)
    
    def has_sub_products(self):
        return self.sub_products.exists()

    def get_sub_products(self):
        return self.sub_products.filter(is_available=True).order_by('id')

    def get_starting_price(self):
        if self.has_sub_products():
            subs = self.get_sub_products()
            if subs.exists():
                return min(p.toman_price() for p in subs)
        return self.toman_price()

    def get_starting_price_display(self):
        return "{:,}".format(int(self.get_starting_price()))

    def get_variant_title(self):
        name = self.name or ''
        slug = self.slug or ''
        if "سه ماه" in name or "3 ماه" in name or "3-month" in slug:
            return "اشتراک ۳ ماهه"
        elif "شش ماه" in name or "6 ماه" in name or "6-month" in slug:
            return "اشتراک ۶ ماهه"
        elif "دوازده ماه" in name or "12 ماه" in name or "یک سال" in name or "12-month" in slug:
            return "اشتراک ۱۲ ماهه (یک‌ساله)"
        elif "یک ماه" in name or "1 ماه" in name or "1-month" in slug:
            return "اشتراک ۱ ماهه"
        return name

    def get_variant_badge(self):
        name = self.name or ''
        slug = self.slug or ''
        if "سه ماه" in name or "3 ماه" in name or "3-month" in slug:
            return "اقتصادی"
        elif "شش ماه" in name or "6 ماه" in name or "6-month" in slug:
            return "محبوب‌ترین"
        elif "دوازده ماه" in name or "12 ماه" in name or "12-month" in slug:
            return "بیشترین تخفیف 🔥"
        return ""

    def get_price_display(self):
        if self.has_sub_products():
            return self.get_starting_price_display()
        return "{:,}".format(int(self.toman_price()))

    def get_exact_count_price(self):
        return int(self.exact_count * (self.toman_price() / 1000))

    def get_exact_count_price_display(self):
        return "{:,}".format(int(self.get_exact_count_price()))

    def get_per_price_display(self):
        return "{:,}".format(int(self.per_price()))

    def get_formatted_price(self):
        if self.exact_count and self.exact_count > 0:
            return self.get_exact_count_price_display()
        return self.get_price_display()

    @property
    def formatted_price(self):
        return self.get_formatted_price()

    @property
    def toman_price_display(self):
        return self.get_price_display()

    @property
    def exact_count_price_display(self):
        return self.get_exact_count_price_display()

    def get_app_display(self):
        return dict(self.APP_CHOICES).get(self.app, "Unknown")
        
    def is_telegram_premium(self):
        text_to_check = f"{self.name or ''} {self.en or ''} {self.slug or ''}".lower()
        return "پرمیوم" in text_to_check or "premium" in text_to_check or "permium" in text_to_check

    def get_500_price(self):
        return int(self.toman_price() * 500 / 1000)

    def get_500_price_display(self):
        return "{:,}".format(int(self.get_500_price()))

    @property
    def price_500(self):
        return self.get_500_price()

    @property
    def price_500_display(self):
        return self.get_500_price_display()

    def is_follower_or_member(self):
        text_to_check = f"{self.name or ''} {self.en or ''} {self.slug or ''}".lower()
        keywords = ["فالوور", "فالور", "follower", "followers", "ممبر", "member", "members", "عضو"]
        return any(kw in text_to_check for kw in keywords)

    def get_absolute_url(self):
        return f"/services/{self.slug}/"
    
    def save(self, *args, **kwargs):
        if self.description:
            self.description = self.description.replace('\\r\\n', '\n').replace('\\n', '\n').replace('\r\n', '\n')
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1

            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "محصول"
        verbose_name_plural = "محصول ها"

    def __str__(self):
        return self.name

class DiscountCode(models.Model):
    DISCOUNT_TYPE_CHOICES = (
        ("percent", "درصدی"),
        ("fixed", "مبلغ ثابت (تومان)"),
    )
    code = models.CharField(
        max_length=50, unique=True, verbose_name="کد تخفیف")
    discount_type = models.CharField(
        max_length=10, choices=DISCOUNT_TYPE_CHOICES, default="percent", verbose_name="نوع تخفیف")
    value = models.PositiveIntegerField(
        verbose_name="مقدار تخفیف (درصد یا تومان)")
    max_discount = models.PositiveBigIntegerField(
        default=0, verbose_name="حداکثر سقف تخفیف به تومان (۰ = بدون سقف)")
    min_order_amount = models.PositiveBigIntegerField(
        default=0, verbose_name="حداقل مبلغ سفارش به تومان (۰ = بدون حداقل)")
    usage_limit = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="سقف کل دفعات استفاده (خالی = نامحدود)")
    used_count = models.PositiveIntegerField(
        default=0, verbose_name="تعداد دفعات استفاده شده")
    user_limit = models.PositiveIntegerField(
        default=1,
        verbose_name="تعداد مجاز استفاده به ازای هر شماره تلفن",
        help_text="تعیین کنید هر کاربر بر اساس شماره تلفنی که وارد می‌کند، حداکثر چند بار مجاز است از این کد تخفیف استفاده کند (مثلاً ۱ یا ۲ بار یا بیشتر). عدد ۰ یعنی بدون محدودیت تعداد."
    )
    valid_from = models.DateTimeField(
        null=True, blank=True, verbose_name="تاریخ شروع اعتبار")
    valid_to = models.DateTimeField(
        null=True, blank=True, verbose_name="تاریخ انقضا")
    is_active = models.BooleanField(
        default=True, verbose_name="فعال است؟")
    products = models.ManyToManyField(
        Product, blank=True, verbose_name="محصولات مجاز (خالی = همه محصولات)")
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        verbose_name = "کد تخفیف"
        verbose_name_plural = "کدهای تخفیف"
        ordering = ["-created_at"]

    def __str__(self):
        val_str = f"{self.value}%" if self.discount_type == "percent" else f"{self.value:,} تومان"
        return f"{self.code} ({val_str})"

    def clean(self):
        from .utils import to_english_digits
        if self.code:
            self.code = to_english_digits(str(self.code)).strip().upper()
        if self.discount_type == "percent" and self.value > 100:
            raise ValidationError({'value': 'درصد تخفیف نمی‌تواند بیشتر از ۱۰۰ باشد.'})

    def save(self, *args, **kwargs):
        from .utils import to_english_digits
        if self.code:
            self.code = to_english_digits(str(self.code)).strip().upper()
        super().save(*args, **kwargs)

    def calculate_discount(self, original_price):
        try:
            original_price = int(original_price or 0)
        except Exception:
            original_price = 0

        max_limit = int(self.max_discount or 0)

        if self.discount_type == "percent":
            discount = int(original_price * (self.value / 100.0))
            if max_limit > 0:
                discount = min(discount, max_limit)
        else:
            discount = min(self.value, original_price)
            if max_limit > 0:
                discount = min(discount, max_limit)
        return max(0, int(discount))

    def is_valid_for(self, amount, user_phone=None, product=None, user=None):
        now = timezone.now()
        if not self.is_active:
            return False, "این کد تخفیف غیرفعال است.", 0

        if self.valid_from and now < self.valid_from:
            return False, "مهلت استفاده از این کد تخفیف هنوز آغاز نشده است.", 0

        if self.valid_to and now > self.valid_to:
            return False, "مهلت استفاده از این کد تخفیف به پایان رسیده است.", 0

        if self.usage_limit is not None and self.used_count >= self.usage_limit:
            return False, "سقف مجاز استفاده از این کد تخفیف به پایان رسیده است.", 0

        if self.min_order_amount and self.min_order_amount > 0:
            if amount < self.min_order_amount:
                return False, f"حداقل مبلغ سفارش برای این کد تخفیف {self.min_order_amount:,} تومان است.", 0

        if self.products.exists() and product:
            if not self.products.filter(id=product.id).exists():
                return False, "این کد تخفیف برای سرویس انتخاب‌شده قابل استفاده نیست.", 0

        if self.user_limit and self.user_limit > 0:
            import re
            persian_digits = '۰۱۲۳۴۵۶۷۸۹'
            arabic_digits = '٠١٢٣٤٥٦٧٨٩'
            english_digits = '0123456789'
            trans = str.maketrans(persian_digits + arabic_digits, english_digits * 2)

            phone_candidates = set()
            phone_10 = None
            display_phone = ""

            if user_phone:
                phone_clean = str(user_phone).strip()
                display_phone = phone_clean
                digits = re.sub(r'\D', '', phone_clean.translate(trans))
                if digits:
                    phone_10 = digits[-10:] if len(digits) >= 10 else digits
                    phone_candidates.update(['0' + phone_10, phone_10, '+98' + phone_10, '98' + phone_10])

            if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
                u_phone = getattr(user, 'phone_number', None)
                if u_phone:
                    if not display_phone:
                        display_phone = str(u_phone).strip()
                    u_digits = re.sub(r'\D', '', str(u_phone).translate(trans))
                    if u_digits:
                        u_10 = u_digits[-10:] if len(u_digits) >= 10 else u_digits
                        phone_candidates.update(['0' + u_10, u_10, '+98' + u_10, '98' + u_10])

            user_query = models.Q()
            if phone_candidates:
                cands_list = list(phone_candidates)
                user_query |= models.Q(receiver_phone__in=cands_list)
                user_query |= models.Q(user__phone_number__in=cands_list)
                if phone_10:
                    user_query |= models.Q(receiver_phone__endswith=phone_10)
                    user_query |= models.Q(user__phone_number__endswith=phone_10)

            if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
                user_query |= models.Q(user=user)

            if user_query:
                # Count orders with status 2 (waiting approval), 3 (in progress), 4 (completed), 5 (cancelled after use)
                # plus orders created in the last 15 minutes that are in status 1 (pending payment)
                recent_pending = now - timezone.timedelta(minutes=15)
                status_query = models.Q(status__in=["2", "3", "4", "5"]) | models.Q(status="1", order_date__gte=recent_pending)

                used_by_user = self.orders.filter(user_query).filter(status_query).count()

                if used_by_user >= self.user_limit:
                    lbl = f" برای شماره {display_phone}" if display_phone else ""
                    return False, f"این کد تخفیف قبلاً به حداکثر تعداد مجاز ({self.user_limit} بار){lbl} استفاده شده است.", 0

        discount = self.calculate_discount(amount)
        return True, "کد تخفیف معتبر است.", discount
    
class Order(models.Model):
    STATUS_CHOICES = (
        ("1", "در انتظار پرداخت"),
        ("2", "در انتظار تایید"),
        ("3", "درحال انجام"),
        ("4", "تکمیل شد"),
        ("5", "لغو شده"),
    )

    PAYMENT_CHOICES = (
        ("zarinpal", "درگاه زرین پال"),
        ("trx", "رمز ارز ترون"),
        ("sizpay", "درگاه سیزپی"),
        ("zibal", "درگاه زیبال"),
        ("userbalance", "موجودی حساب"),
    )
    user = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="کاربر")
    code = models.CharField(
        max_length=50, verbose_name="کد پیگیری")
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, verbose_name="محصول")
    receiver_phone = models.CharField(
        max_length=11, verbose_name="شماره تحویل گیرنده")
    page_address = models.CharField(
        max_length=500, verbose_name="آدرس صفحه")
    count_order = models.PositiveBigIntegerField(
        verbose_name="تعداد سفارش")
    start_followers_count = models.PositiveBigIntegerField(
        default=0,
        blank=True,
        verbose_name="تعداد فالوور در هنگام شروع سفارش")
    has_bump = models.BooleanField(
        default=False,
        verbose_name="سفارش مکمل (Order Bump)")
    bump_posts_count = models.PositiveIntegerField(
        default=0,
        verbose_name="تعداد پست‌های مکمل")
    bump_likes_each = models.PositiveIntegerField(
        default=0,
        verbose_name="تعداد لایک به ازای هر پست")
    bump_views_each = models.PositiveIntegerField(
        default=0,
        verbose_name="تعداد ویو به ازای هر پست")
    bump_price = models.PositiveBigIntegerField(
        default=0,
        verbose_name="مبلغ سفارش مکمل (تومان)")
    bump_details = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="جزئیات بسته مکمل")
    order_full_price = models.PositiveBigIntegerField(
        verbose_name="قیمت کل سفارش")
    original_price = models.PositiveBigIntegerField(
        default=0, verbose_name="مبلغ اولیه سفارش")
    coupon = models.ForeignKey(
        DiscountCode, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders", verbose_name="کد تخفیف")
    discount_amount = models.PositiveBigIntegerField(
        default=0, verbose_name="مبلغ تخفیف")
    order_date = models.DateTimeField(
        auto_now_add=True, verbose_name="تاریخ سفارش")
    order_finish_date = models.DateTimeField(
        verbose_name="تاریخ تکمیل سفارش", null=True, blank=True)
    payment_method = models.CharField(
        max_length=100, choices=PAYMENT_CHOICES, verbose_name="روش پرداخت", null=True, blank=True)
    authority = models.CharField(
        max_length=200, verbose_name="کد پرداخت")
    orderid = models.CharField(
        max_length=100, verbose_name="شماره سفارش", default="سفارش ثبت نشده")
    status = models.CharField(
        max_length=1, choices=STATUS_CHOICES, verbose_name="وضعیت", default=1)
    discount_sms_sent = models.BooleanField(
        default=False, verbose_name="پیامک تخفیف ارسال شده")
    discount_sms_sent_at = models.DateTimeField(
        null=True, blank=True, verbose_name="زمان ارسال پیامک تخفیف")

    def send_discount_sms(self):
        from .utils import send_discount_coupon_sms
        phone = (self.receiver_phone or (self.user.phone_number if self.user else "")).strip()
        if not phone:
            return False, "شماره تماس یافت نشد"
        ok = send_discount_coupon_sms(phone)
        if ok:
            self.discount_sms_sent = True
            self.discount_sms_sent_at = timezone.now()
            self.save(update_fields=["discount_sms_sent", "discount_sms_sent_at"])
            return True, "ارسال شد"
        return False, "خطا در ارسال پیامک"

    def get_date(self):
        if self.order_date:
            local_time = self._safe_localtime(self.order_date)
            j_date = jdatetime.datetime.fromgregorian(datetime=local_time)
            months = [
                "",
                "فروردین", "اردیبهشت", "خرداد",
                "تیر", "مرداد", "شهریور",
                "مهر", "آبان", "آذر",
                "دی", "بهمن", "اسفند"
            ]
            formatted_date = f"{j_date.day} {months[j_date.month]} {j_date.year}"
            return formatted_date
        return ""
        
    @staticmethod
    def _safe_localtime(value):
        if timezone.is_naive(value):
            return value
        return timezone.localtime(value)
    
    def get_order_status(self):
        STATUS_CHOICES = (
            ("1", "در انتظار پرداخت"),
            ("2", "در انتظار تایید"),
            ("3", "درحال انجام"),
            ("4", "تکمیل شد"),
            ("5", "لغو شده"),
        )
        app_name = dict(STATUS_CHOICES).get(self.status, "Unknown")
        return app_name
        
    def get_order_status_en(self):
        STATUS_CHOICES = (
            ("1", "pay"),
            ("2", "confirm"),
            ("3", "process"),
            ("4", "complete"),
            ("5", "cancel"),
        )
        app_name = dict(STATUS_CHOICES).get(self.status, "Unknown")
        return app_name
        
    def get_numberformat_price(self):
        return "{:,}".format(self.order_full_price)
        
    def generate_code(self, length=32):
        chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        return ''.join(random.choice(chars) for _ in range(length))
    
    def save(self, *args, **kwargs):
        from .utils import to_english_digits
        if self.receiver_phone:
            self.receiver_phone = to_english_digits(str(self.receiver_phone)).strip()
        if self.code:
            self.code = to_english_digits(str(self.code)).strip()
        if self.orderid:
            self.orderid = to_english_digits(str(self.orderid)).strip()
        if self.authority:
            self.authority = to_english_digits(str(self.authority)).strip()
        if self.count_order is not None:
            try:
                self.count_order = int(to_english_digits(str(self.count_order)))
            except (ValueError, TypeError):
                pass
        if self.start_followers_count is not None:
            try:
                self.start_followers_count = int(to_english_digits(str(self.start_followers_count)))
            except (ValueError, TypeError):
                self.start_followers_count = 0
        else:
            self.start_followers_count = 0
        if not self.code:
            self.code = get_random_string(length=8)
            while Order.objects.filter(code=self.code).exists():
                self.code = get_random_string(length=8)
        if self.original_price is None:
            if self.product.en == 'data' or self.product.en == 'charge':
                self.original_price = int(self.product.toman_price() * self.count_order)
            else:
                self.original_price = int(self.product.toman_price() * self.count_order / 1000)
        if self.order_full_price is None:
            if self.coupon and self.discount_amount:
                self.order_full_price = max(0, self.original_price - self.discount_amount)
            else:
                self.order_full_price = self.original_price
        if not self.payment_method:
            self.payment_method = "zibal"
        if not self.authority and (self.order_full_price and self.order_full_price > 0):
            self.generate_authority()
        super(Order, self).save(*args, **kwargs)

    def generate_authority(self):
        site_settings = SiteSettings.objects.first()
        domain = site_settings.domain if (site_settings and site_settings.domain) else "localhost:8000"
        scheme = "http" if ("localhost" in domain or "127.0.0.1" in domain) else "https"
        callback_uri = f"{scheme}://{domain}/verify"

        if self.payment_method == "zarinpal":
            merchant_id = site_settings.zarinpal_merchant_id if (site_settings and site_settings.zarinpal_merchant_id not in ['notset', '', None]) else getattr(settings, 'ZARINPAL_MERCHANT', '')
            data = {
                "merchant_id": merchant_id,
                "amount": self.order_full_price * 10,
                "description": f'پرداخت سفارش : {self.code}',
                "callback_url": callback_uri,
            }
            data = json.dumps(data)
            headers = {'content-type': 'application/json', 'content-length': str(len(data)) }
            try:
                response = requests.post(settings.ZARINPAL_API_REQUEST, data=data,headers=headers, timeout=10)
                if response.status_code == 200:
                    response = response.json()
                    if response['data']['code'] == 100:
                        self.authority = response['data']['authority']
                        return True
                    else:
                        return False
                return response
            except requests.exceptions.Timeout:
                return False
            except requests.exceptions.ConnectionError:
                return False
        elif self.payment_method == "sizpay":
            data = {
                "sizPayKey": site_settings.sizpay_merchant_id if (site_settings and site_settings.sizpay_merchant_id not in ['notset', '', None]) else getattr(settings, 'SIZPAY_MERCHANT', ''),
                "ReturnURL": callback_uri,
                "Amount": self.order_full_price * 10,
                "OrderID": int(time.time()),
                "InvoiceNo": str(self.code),
                "DocDate": "",
                "ExtraInf": f"پرداخت سفارش {self.code}",
                "AppExtraInf": {
                    "PayerNm": "",
                    "PayerMobile": self.receiver_phone or "",
                    "PayerEmail": "",
                    "Descr": f"سفارش شماره {self.code}",
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
                        return True
                return False

            except requests.exceptions.Timeout:
                return False
            except requests.exceptions.ConnectionError:
                return False
            except Exception:
                return False
        elif self.payment_method == "zibal":
            url = f"https://gateway.zibal.ir/v1/request"
            merchant_id = site_settings.zibal_merchant_id if (site_settings and site_settings.zibal_merchant_id not in ['notset', '', None]) else getattr(settings, 'ZIBAL_MERCHANT', 'zibal')
            payer_phone = str(self.receiver_phone or (self.user.phone_number if self.user else "")).strip()
            desc = f"پرداخت سفارش شماره {self.code}"
            if payer_phone:
                desc += f" - شماره {payer_phone}"
            parameters = {
                "merchant": merchant_id,
                "callbackUrl": callback_uri,
                "orderId": str(self.code),
                "description": desc,
                "amount": self.order_full_price * 10
            }
            if payer_phone:
                parameters["mobile"] = payer_phone
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
                    return True
                return False
            except requests.exceptions.Timeout:
                return False
            except requests.exceptions.ConnectionError:
                return False
            except Exception:
                return False
        elif self.payment_method == "trx":
            self.authority = self.generate_code()
            return True

    class Meta:
        verbose_name = "سفارش"
        verbose_name_plural = "سفارش‌ها"

    def __str__(self) -> str:
        return f"برنامه: {self.product.get_app_display()} - محصول: {self.product.name} - تعداد: {self.count_order} ({dict(self.STATUS_CHOICES)[self.status]})"

    def is_follower_or_member(self):
        """بررسی اینکه آیا سرویس سفارش از نوع فالوور یا ممبر است"""
        if not self.product:
            return False
        text_to_check = f"{self.product.name} {self.product.en or ''} {self.product.slug or ''}".lower()
        keywords = ["فالوور", "فالور", "follower", "followers", "ممبر", "member", "members", "عضو"]
        return any(kw in text_to_check for kw in keywords)

    def is_refill_eligible_product(self):
        """شرایط کلی مجاز بودن جبران ریزش: سرویس فالوور یا ممبر باشد و وضعیت سفارش تایید/درحال انجام/تکمیل باشد"""
        return self.is_follower_or_member() and str(self.status) in ["2", "3", "4"]

    def can_request_refill(self):
        """آیا ۱ روز (۲۴ ساعت) از ثبت سفارش گذشته است؟"""
        if not self.is_refill_eligible_product():
            return False
        if not self.order_date:
            return False
        diff_seconds = (timezone.now() - self.order_date).total_seconds()
        return diff_seconds >= 86400

    def refill_unlock_remaining_seconds(self):
        """ثانیه‌های باقی‌مانده تا پایان ۲۴ ساعت"""
        if not self.order_date:
            return 0
        diff_seconds = (timezone.now() - self.order_date).total_seconds()
        return max(0, int(86400 - diff_seconds))

    def refill_unlock_remaining_hours_text(self):
        secs = self.refill_unlock_remaining_seconds()
        if secs <= 0:
            return ""
        hours = math.ceil(secs / 3600)
        return f"حدود {hours} ساعت دیگر"

    @property
    def latest_refill_request(self):
        return self.refill_requests.order_by('-created_at').first()

class SiteSettings(models.Model):
    commission_percent = models.FloatField(verbose_name="پورسانت فروش (درصد)", default=20)
    enable_sizpay = models.BooleanField("درگاه سیزپی", default=False)
    enable_zarinpal = models.BooleanField("درگاه زرین پال", default=True)
    enable_zibal = models.BooleanField("درگاه زیبال", default=True)
    enable_trx = models.BooleanField("درگاه ترون", default=True)
    enable_card = models.BooleanField("کارت به کارت", default=True)
    card_number = models.CharField(max_length=100, verbose_name="شماره کارت", default="notset")
    card_name = models.CharField(max_length=500, verbose_name="نام صاحب کارت", default="notset")
    zarinpal_merchant_id = models.CharField(max_length=500, verbose_name="مرچنت زرین‌پال (zarinpal.com)", default="notset")
    zibal_merchant_id = models.CharField(max_length=500, verbose_name="مرچنت زیبال(zibal.ir)", default="notset")
    sizpay_merchant_id = models.CharField(max_length=500, verbose_name="مرچنت سیزپی (sizpay.ir)", default="notset")
    tron_wallet_address = models.CharField(max_length=500, verbose_name="آدرس کیف پول ترون (TronLink)", default="notset")
    panel_api_key = models.CharField(max_length=500, verbose_name="API KEY پنل خدمات (justanotherpanel.com)", default="notset")
    sms_api_key = models.CharField(max_length=500, verbose_name="API KEY پنل پیامک (sms.ir)", default="notset")
    support_api_key = models.CharField(max_length=500, verbose_name="API KEY پنل پشتیبانی (crisp.chat)", default="notset")
    sms_pattern_otp = models.CharField(max_length=100, verbose_name="کد پترن پیامک otp", default="notset")
    sms_pattern_code_user = models.CharField(max_length=100, verbose_name="کد پترن پیامک کاربر", default="notset")
    sms_pattern_code_admin = models.CharField(max_length=100, verbose_name="کد پترن پیامک ادمین", default="notset")
    sms_pattern_code_cancel = models.CharField(max_length=100, verbose_name="کد پترن پیامک کنسل شدن", default="notset")
    sms_pattern_code_complete = models.CharField(max_length=100, verbose_name="کد پترن پیامک تکمیل شدن", default="notset")
    sms_pattern_code_refill = models.CharField(max_length=100, verbose_name="کد پترن پیامک ثبت درخواست جبران ریزش", default="602209", help_text="کد قالب پیامک SMS.ir برای اطلاع‌رسانی ثبت درخواست جبران ریزش (متغیر ORDERID)")
    admin_phone_number = models.CharField(max_length=15, verbose_name="شماره موبایل ادمین 09", default="notset")
    whatsapp_phone_number = models.CharField(max_length=500, verbose_name="شماره پشتیبانی در واتساپ", default="notset")
    name = models.CharField(max_length=500, verbose_name="نام سایت", default="پنل")
    domain = models.CharField(max_length=500, verbose_name="دامنه سایت", default="example.com")
    recaptcha_site_key = models.CharField(max_length=500, verbose_name="SITE KEY کپچا گوگل", default="notset")
    recaptcha_secret_key = models.CharField(max_length=500, verbose_name="SECRET KEY کپچا گوگل", default="notset")
    enamad = models.CharField(max_length=500, verbose_name="اینماد (enamad.ir)", default="notset")
    telegram_page = models.CharField(max_length=500, verbose_name="کانال تلگرام (https://t.me)", default="https://t.me")
    instagram_page = models.CharField(max_length=500, verbose_name="پیج اینستاگرام (https://instagram.com)", default="https://instagram.com")
    twitter_page = models.CharField(max_length=500, verbose_name="پیج توییتر (https://x.com)", default="https://x.com")
    footer_description = models.CharField(max_length=3000, verbose_name="توضیحات فوتر", default="بهترین و ارزان ترین سایت افزایش ممبر و ویو تلگرام، فالور و لایک اینستاگرام، سابسکرایب و لایک یوتیوب و ...")
    
    class Meta:
        verbose_name = "تنظیمات سایت"
        verbose_name_plural = "تنظیمات سایت"

    def __str__(self):
        return "تنظیمات سایت"
    
    def get_panel_balance(self):
        from .utils import get_balance
        try:
            return float(get_balance())
        except:
            return 0
            
class Wallet(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, verbose_name="سفارش")
    wallet_address = models.CharField(max_length=500, verbose_name="آدرس کیف پول", default="notset")
    public_key = models.CharField(max_length=500, verbose_name="پابلیک کی", default="notset")
    private_key = models.CharField(max_length=500, verbose_name="پرایوت کی", default="notset")
    
    def generate_payment(self, order):
        from .utils import generate_trx_wallet
        self.order = order
        self.wallet_address, self.private_key, self.public_key = generate_trx_wallet()
        return True
        
    def confirm_payment(self):
        stsetting = SiteSettings.objects.first()
        from .utils import get_trx_balance, get_trx_price, transfer_balance
        balance = get_trx_balance(self.wallet_address)
        b = int(balance)/1000000
        trx_amount = (int(balance)-1200000)/1000000
        rial = int(get_trx_price() * (b))
        if rial >= self.order.order_full_price:
            transfer_balance(self.wallet_address, self.private_key, stsetting.tron_wallet_address)
            return True
        return False
    
    class Meta:
        verbose_name = "کیف پول ارزی"
        verbose_name_plural = "کیف پول های ارزی"
    
    def __str__(self):
        return "کیف پول ارزی"

class FAQ(models.Model):
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='faqs',
        verbose_name='محصول'
    )
    question = models.CharField(
        max_length=255,
        verbose_name='سوال'
    )
    answer = models.TextField(
        verbose_name='پاسخ'
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='ترتیب نمایش',
        help_text='عدد کمتر، بالاتر نمایش داده می‌شود'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='فعال'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاریخ بروزرسانی'
    )

    class Meta:
        verbose_name = 'سوال متداول'
        verbose_name_plural = 'سوالات متداول'
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['product', 'is_active']),
        ]

    def __str__(self):
        return f"{self.question} ({self.product.name})"

    def clean(self):
        if not self.question.strip():
            raise ValidationError({'question': 'سوال نمی‌تواند خالی باشد.'})
        if not self.answer.strip():
            raise ValidationError({'answer': 'پاسخ نمی‌تواند خالی باشد.'})
            
class NotifyRequest(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="notify_requests"
    )
    phone = models.CharField(max_length=11, verbose_name="شماره تلفن")
    is_notified = models.BooleanField(default=False, verbose_name="پیامک ارسال شد؟")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "درخواست اطلاع‌رسانی"
        verbose_name_plural = "درخواست‌های اطلاع‌رسانی"
        unique_together = ("product", "phone")

    def __str__(self):
        return f"{self.phone} - {self.product.name}"

class RefillRequest(models.Model):
    STATUS_CHOICES = (
        ("pending", "در انتظار بررسی"),
        ("processing", "در حال انجام"),
        ("completed", "تکمیل شده"),
        ("rejected", "رد شده"),
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="refill_requests",
        verbose_name="سفارش"
    )
    user_phone = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="شماره تماس کاربر"
    )
    page_address = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="لینک / پیج مقصد"
    )
    product_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="عنوان سرویس"
    )
    count_order = models.PositiveBigIntegerField(
        default=0,
        blank=True,
        verbose_name="تعداد سفارش"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="وضعیت جبران ریزش"
    )
    user_description = models.TextField(
        null=True,
        blank=True,
        verbose_name="توضیحات کاربر"
    )
    admin_note = models.TextField(
        null=True,
        blank=True,
        verbose_name="توضیحات / یادداشت مدیر"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ثبت درخواست"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="تاریخ آخرین بروزرسانی"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="تاریخ تکمیل جبران"
    )

    class Meta:
        verbose_name = "درخواست جبران ریزش"
        verbose_name_plural = "درخواست‌های جبران ریزش"
        ordering = ["-created_at"]

    def __str__(self):
        try:
            code = self.order.code if self.order else str(self.order_id)
        except Exception:
            code = str(self.order_id)
        return f"جبران ریزش سفارش {code} - {self.get_status_display()}"

    def get_status_badge_class(self):
        badges = {
            "pending": "warning",
            "processing": "info",
            "completed": "success",
            "rejected": "danger",
        }
        return badges.get(self.status, "secondary")

    def get_created_date(self):
        if self.created_at:
            local_time = Order._safe_localtime(self.created_at)
            j_date = jdatetime.datetime.fromgregorian(datetime=local_time)
            months = [
                "",
                "فروردین", "اردیبهشت", "خرداد",
                "تیر", "مرداد", "شهریور",
                "مهر", "آبان", "آذر",
                "دی", "بهمن", "اسفند"
            ]
            return f"{j_date.day} {months[j_date.month]} {j_date.year} ساعت {j_date.strftime('%H:%M')}"
        return ""

    def get_completed_date(self):
        if self.completed_at:
            local_time = Order._safe_localtime(self.completed_at)
            j_date = jdatetime.datetime.fromgregorian(datetime=local_time)
            months = [
                "",
                "فروردین", "اردیبهشت", "خرداد",
                "تیر", "مرداد", "شهریور",
                "مهر", "آبان", "آذر",
                "دی", "بهمن", "اسفند"
            ]
            return f"{j_date.day} {months[j_date.month]} {j_date.year} ساعت {j_date.strftime('%H:%M')}"
        return ""

    def send_completion_sms(self):
        phone = (self.user_phone or "").strip()
        if not phone and self.order and self.order.receiver_phone:
            phone = str(self.order.receiver_phone).strip()
        order_id = self.order.code if self.order else ""
        if phone and order_id:
            try:
                from .utils import send_refill_completed_sms
                return send_refill_completed_sms(phone=phone, orderid=order_id)
            except Exception as e:
                print(f"Error in send_completion_sms: {e}")
        return False

    def save(self, *args, **kwargs):
        from .utils import to_english_digits
        # Auto-fill missing fields from associated order if available
        if hasattr(self, 'order') and self.order:
            if not self.user_phone and getattr(self.order, 'receiver_phone', None):
                self.user_phone = str(self.order.receiver_phone).strip()
            if not self.page_address and getattr(self.order, 'page_address', None):
                self.page_address = str(self.order.page_address).strip()
            if not self.product_name and getattr(self.order, 'product', None):
                self.product_name = str(self.order.product.name).strip()
            if (not self.count_order or self.count_order == 0) and getattr(self.order, 'count_order', None):
                self.count_order = self.order.count_order

        if self.user_phone:
            self.user_phone = to_english_digits(str(self.user_phone)).strip()
        if self.count_order is not None:
            try:
                self.count_order = int(to_english_digits(str(self.count_order)))
            except (ValueError, TypeError):
                pass
        super().save(*args, **kwargs)



class ChatSession(models.Model):
    session_key = models.CharField(max_length=64, unique=True, verbose_name="کلید سشن")
    name = models.CharField(max_length=150, blank=True, default="", verbose_name="نام کاربر")
    phone_or_email = models.CharField(max_length=150, blank=True, default="", verbose_name="شماره تماس یا ایمیل")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="کاربر سایت")
    telegram_thread_msg_id = models.BigIntegerField(null=True, blank=True, verbose_name="شناسه پیام هدر در تلگرام")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ شروع")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین بروزرسانی")
    is_closed = models.BooleanField(default=False, verbose_name="بسته شده")

    class Meta:
        db_table = "chat_session"
        verbose_name = "گفتگوی آنلاین"
        verbose_name_plural = "گفتگوهای آنلاین"
        ordering = ["-updated_at"]

    def __str__(self):
        user_info = self.name or self.phone_or_email or (self.user.phone_number if self.user else "کاربر مهمان")
        return f"گفتگو #{self.id} - {user_info}"


class ChatMessage(models.Model):
    class Sender(models.TextChoices):
        USER = "user", "کاربر"
        ADMIN = "admin", "پشتیبان"

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages", verbose_name="گفتگو")
    sender = models.CharField(max_length=10, choices=Sender.choices, default=Sender.USER, verbose_name="فرستنده")
    text = models.TextField(verbose_name="متن پیام")
    is_read = models.BooleanField(default=False, verbose_name="خوانده شده")
    telegram_msg_id = models.BigIntegerField(null=True, blank=True, verbose_name="شناسه پیام تلگرام")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ارسال")

    class Meta:
        db_table = "chat_message"
        verbose_name = "پیام گفتگو"
        verbose_name_plural = "پیام‌های گفتگو"
        ordering = ["created_at"]

    def __str__(self):
        return f"پیام #{self.id} ({self.get_sender_display()}): {self.text[:30]}"
