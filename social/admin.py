from django.contrib import admin
from .models import Product, Order, SiteSettings, Wallet, FAQ, DiscountCode, RefillRequest, ChatSession, ChatMessage
from django.utils import timezone
from .utils import send_order_complete, send_refill_completed_sms, send_discount_coupon_sms
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import redirect
from django.contrib import messages

@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "discount_type",
        "value_display",
        "user_limit_display",
        "max_discount_display",
        "min_order_display",
        "used_count",
        "usage_limit",
        "is_active",
        "valid_to"
    ]
    list_filter = ["discount_type", "is_active", "valid_from", "valid_to"]
    search_fields = ["code"]
    filter_horizontal = ["products"]
    readonly_fields = ["used_count", "created_at"]
    ordering = ["-created_at"]

    fieldsets = (
        ("اطلاعات اصلی کد تخفیف", {
            "fields": ("code", "discount_type", "value", "is_active"),
        }),
        ("محدودیت استفاده به ازای هر شماره تلفن (کاربر)", {
            "fields": ("user_limit",),
            "description": "با این فیلد تعیین کنید هر کاربر بر اساس شماره تلفنی که موقع ثبت سفارش وارد می‌کند، حداکثر چند بار مجاز است از این کد تخفیف استفاده کند (مثلاً ۱ یا ۲ بار). عدد ۰ یا خالی به معنی بدون محدودیت است."
        }),
        ("سایر شرایط و محدودیت‌ها", {
            "fields": ("max_discount", "min_order_amount", "usage_limit", "products"),
            "description": "در صورتی که مقداری وارد نشود یا ۰ باشد، محدودیتی اعمال نخواهد شد."
        }),
        ("بازه زمانی اعتبار", {
            "fields": ("valid_from", "valid_to"),
        }),
        ("آمار و تاریخچه", {
            "fields": ("used_count", "created_at"),
        }),
    )

    def value_display(self, obj):
        if obj.discount_type == "percent":
            return f"{obj.value} %"
        return f"{obj.value:,} تومان"
    value_display.short_description = "مقدار تخفیف"

    def user_limit_display(self, obj):
        if obj.user_limit and obj.user_limit > 0:
            return f"{obj.user_limit} بار برای هر شماره"
        return "نامحدود"
    user_limit_display.short_description = "سقف هر شماره تلفن"

    def max_discount_display(self, obj):
        if obj.max_discount and obj.max_discount > 0:
            return f"{obj.max_discount:,} تومان"
        return "بدون سقف"
    max_discount_display.short_description = "سقف تخفیف"

    def min_order_display(self, obj):
        if obj.min_order_amount and obj.min_order_amount > 0:
            return f"{obj.min_order_amount:,} تومان"
        return "بدون حداقل"
    min_order_display.short_description = "حداقل خرید"

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "app", "price", "max_order", "selled_count", "get_discounted_price"]
    list_filter = ["app"]
    readonly_fields = ["selled_count"]
    search_fields = ["name", "description"]
    ordering = ["name"]
    filter_horizontal = ["sub_products"]

    def get_discounted_price(self, obj):
        discounted_price = obj.price - (obj.price * obj.discount / 100)
        return f"{discounted_price:,} دلار"

    get_discounted_price.short_description = "قیمت با تخفیف"

class RefillRequestInline(admin.TabularInline):
    model = RefillRequest
    extra = 0
    can_delete = True
    readonly_fields = ["created_at"]
    fields = ["status", "product_name", "count_order", "page_address", "user_phone", "user_description", "admin_note", "created_at", "completed_at"]
    ordering = ["-created_at"]
    verbose_name = "درخواست جبران ریزش"
    verbose_name_plural = "درخواست‌های جبران ریزش این سفارش"

@admin.register(RefillRequest)
class RefillRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "order_link",
        "user_phone",
        "product_name",
        "count_order",
        "page_address_link",
        "status_badge",
        "created_at_jalali",
        "quick_complete_action"
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["order__code", "user_phone", "page_address", "product_name", "user_description", "admin_note"]
    autocomplete_fields = ["order"]
    ordering = ["-created_at"]
    actions = ["mark_completed", "mark_processing", "mark_rejected"]

    fieldsets = (
        ("مشخصات سفارش و کاربر", {
            "fields": ("order", "user_phone", "product_name", "count_order", "page_address", "user_description"),
            "description": "فقط انتخاب سفارش الزامی است؛ در صورت خالی گذاشتن سایر فیلدها، اطلاعات (شماره تماس، پیج، نام سرویس و تعداد) به صورت خودکار از سفارش انتخابی تکمیل می‌گردد."
        }),
        ("وضعیت و مدیریت جبران ریزش", {
            "fields": ("status", "admin_note", "completed_at"),
            "description": "پس از ارسال فالوور یا ممبر جبرانی، وضعیت را به «تکمیل شده» تغییر دهید."
        }),
        ("اطلاعات زمانی", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ["created_at", "updated_at"]
        return ["order", "created_at", "updated_at"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:refill_id>/complete/', self.admin_site.admin_view(self.complete_refill_view), name='refill_request_complete'),
        ]
        return custom_urls + urls

    def complete_refill_view(self, request, refill_id):
        refill = self.get_object(request, refill_id)
        if refill:
            was_completed = (refill.status == "completed")
            refill.status = "completed"
            refill.completed_at = timezone.now()
            refill.save()
            sms_sent = False
            if not was_completed:
                sms_sent = refill.send_completion_sms()
            if sms_sent:
                messages.success(request, f"درخواست جبران ریزش سفارش {refill.order.code} تکمیل شد و پیامک اطلاع‌رسانی با موفقیت به شماره {refill.user_phone} ارسال گردید.")
            else:
                messages.success(request, f"درخواست جبران ریزش سفارش {refill.order.code} به عنوان «تکمیل شده» ثبت گردید.")
        return redirect(reverse("admin:social_refillrequest_changelist"))

    def order_link(self, obj):
        url = reverse("admin:social_order_change", args=[obj.order.id])
        return format_html('<a href="{}" style="font-weight: bold; color: #0284c7;">{}</a>', url, obj.order.code)
    order_link.short_description = "کد پیگیری سفارش"

    def page_address_link(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener noreferrer" style="color: #2563eb; direction: ltr; display: inline-block;">{}</a>', obj.page_address, obj.page_address[:45] + ("..." if len(obj.page_address) > 45 else ""))
    page_address_link.short_description = "لینک / پیج مقصد"

    def status_badge(self, obj):
        colors = {
            "pending": "#eab308",
            "processing": "#3b82f6",
            "completed": "#10b981",
            "rejected": "#ef4444",
        }
        bg = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 12px; display: inline-block;">{}</span>',
            bg, obj.get_status_display()
        )
    status_badge.short_description = "وضعیت جبران"

    def created_at_jalali(self, obj):
        return obj.get_created_date()
    created_at_jalali.short_description = "تاریخ ثبت"

    def quick_complete_action(self, obj):
        if obj.status == "completed":
            return format_html('<span style="color: #10b981; font-weight: bold;"><i class="fa-solid fa-check-double"></i> انجام شد</span>')
        url = reverse("admin:refill_request_complete", args=[obj.id])
        return format_html(
            '<a href="{}" class="button" style="background: #10b981; color: white; padding: 4px 10px; border-radius: 5px; text-decoration: none; font-size: 12px; font-weight: bold; display: inline-block;"><i class="fa-solid fa-check"></i> تکمیل شد</a>',
            url
        )
    quick_complete_action.short_description = "عملیات سریع"

    def save_model(self, request, obj, form, change):
        is_becoming_completed = False
        if change and obj.pk:
            old_obj = RefillRequest.objects.filter(pk=obj.pk).first()
            if old_obj and old_obj.status != "completed" and obj.status == "completed":
                is_becoming_completed = True
        elif obj.status == "completed":
            is_becoming_completed = True

        if is_becoming_completed and not obj.completed_at:
            obj.completed_at = timezone.now()

        super().save_model(request, obj, form, change)

        if is_becoming_completed:
            obj.send_completion_sms()

    def mark_completed(self, request, queryset):
        count = 0
        sms_count = 0
        for refill in queryset:
            was_completed = (refill.status == "completed")
            refill.status = "completed"
            refill.completed_at = timezone.now()
            refill.save()
            count += 1
            if not was_completed:
                if refill.send_completion_sms():
                    sms_count += 1
        self.message_user(request, f"{count} درخواست جبران ریزش به وضعیت «تکمیل شده» تغییر یافت ({sms_count} پیامک اطلاع‌رسانی ارسال شد).")
    mark_completed.short_description = "تغییر وضعیت موارد انتخاب‌شده به «تکمیل شده» (با ارسال پیامک)"

    def mark_processing(self, request, queryset):
        count = queryset.update(status="processing")
        self.message_user(request, f"{count} درخواست جبران ریزش به وضعیت «در حال انجام» تغییر یافت.")
    mark_processing.short_description = "تغییر وضعیت موارد انتخاب‌شده به «در حال انجام»"

    def mark_rejected(self, request, queryset):
        count = queryset.update(status="rejected")
        self.message_user(request, f"{count} درخواست جبران ریزش به وضعیت «رد شده» تغییر یافت.")
    mark_rejected.short_description = "تغییر وضعیت موارد انتخاب‌شده به «رد شده»"

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["code", "product", "get_product_id", "orderid", "receiver_phone", "status", "start_followers_display", "bump_badge", "discount_sms_badge", "order_date", "original_price", "discount_amount", "order_full_price", "coupon"]
    list_filter = ["status", "has_bump", "discount_sms_sent", "payment_method", "order_date"]
    search_fields = ["code", "receiver_phone", "page_address"]
    ordering = ["-order_date"]
    readonly_fields = ["order_date", "authority", "get_product_id", "original_price", "discount_amount", "discount_sms_sent", "discount_sms_sent_at"]
    actions = ["send_discount_coupon_sms_action"]
    inlines = [RefillRequestInline]

    fieldsets = (
        ("اطلاعات اصلی سفارش", {
            "fields": ("code", "product", "get_product_id", "orderid", "receiver_phone", "page_address", "count_order", "start_followers_count", "original_price", "discount_amount", "order_full_price", "coupon", "order_date", "order_finish_date"),
        }),
        ("سفارش مکمل انتخابی کاربر (Order Bump - انجام دستی توسط ادمین)", {
            "fields": ("has_bump", "bump_details", "bump_posts_count", "bump_likes_each", "bump_views_each", "bump_price"),
            "description": "توجه: این بخش به پرووایدر ارسال خودکار نمی‌شود و جهت انجام دستی توسط شما با جزئیات کامل در اینجا ثبت شده است."
        }),
        ("اطلاعات پرداخت", {
            "fields": ("payment_method", "authority", "status"),
        }),
        ("پیامک کد تخفیف", {
            "fields": ("discount_sms_sent", "discount_sms_sent_at"),
        }),
    )

    def bump_badge(self, obj):
        if getattr(obj, "has_bump", False):
            details = getattr(obj, "bump_details", "") or "سفارش مکمل"
            posts = getattr(obj, "bump_posts_count", 0) or 0
            likes = getattr(obj, "bump_likes_each", 0) or 0
            views = getattr(obj, "bump_views_each", 0) or 0
            summary_txt = f"{posts} پست"
            parts = []
            if likes > 0:
                parts.append(f"{likes:,} لایک")
            if views > 0:
                parts.append(f"{views:,} ویو")
            if parts:
                summary_txt += f" ({' + '.join(parts)})"
            return format_html(
                '<span style="background: linear-gradient(135deg, #f59e0b 0%, #ea580c 100%); color: white; padding: 3px 8px; border-radius: 5px; font-size: 11px; font-weight: bold; white-space: nowrap; display: inline-block;" title="انجام دستی: {}">⚡ مکمل دستی: {}</span>',
                details,
                summary_txt
            )
        return format_html('<span style="color: #94a3b8; font-size: 11px;">ندارد</span>')
    bump_badge.short_description = "سفارش مکمل (دستی)"
    bump_badge.admin_order_field = "has_bump"

    def start_followers_display(self, obj):
        try:
            val = int(getattr(obj, "start_followers_count", 0) or 0)
        except (ValueError, TypeError):
            val = 0
        if val > 0:
            formatted_val = f"{val:,}"
            return format_html('<span style="font-weight: bold; color: #2563eb;">{}</span>', formatted_val)
        return format_html('<span style="color: #94a3b8;">0</span>')
    start_followers_display.short_description = "فالوور شروع"
    start_followers_display.admin_order_field = "start_followers_count"

    def discount_sms_badge(self, obj):
        if obj.discount_sms_sent:
            time_str = ""
            if obj.discount_sms_sent_at:
                try:
                    import jdatetime
                    local_t = timezone.localtime(obj.discount_sms_sent_at)
                    j_t = jdatetime.datetime.fromgregorian(datetime=local_t)
                    time_str = f"<br><small style='color: #64748b; font-size: 10px;'>{j_t.strftime('%Y/%m/%d %H:%M')}</small>"
                except Exception:
                    pass
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; white-space: nowrap;"><i class="fa-solid fa-check"></i> ارسال شده</span>{}',
                format_html(time_str)
            )
        return format_html('<span style="color: #94a3b8; font-size: 11px;">ارسال نشده</span>')
    discount_sms_badge.short_description = "پیامک تخفیف"

    def send_discount_coupon_sms_action(self, request, queryset):
        """
        ارسال پیامک کد تخفیف با پترن 430810 به سفارشات پرداخت‌نشده انتخاب‌شده
        با قابلیت شناسایی و عدم ارسال مجدد به مواردی که قبلاً پیامک دریافت کرده‌اند
        """
        sent_count = 0
        already_sent_count = 0
        failed_count = 0

        for order in queryset:
            if order.discount_sms_sent:
                already_sent_count += 1
                continue

            phone = (order.receiver_phone or (order.user.phone_number if order.user else "")).strip()
            if not phone:
                failed_count += 1
                continue

            ok, _ = order.send_discount_sms()
            if ok:
                sent_count += 1
            else:
                failed_count += 1

        msg_parts = []
        if sent_count > 0:
            msg_parts.append(f"پیامک کد تخفیف با موفقیت به {sent_count} سفارش ارسال شد.")
        if already_sent_count > 0:
            msg_parts.append(f"{already_sent_count} سفارش به دلیل اینکه قبلاً پیامک تخفیف دریافت کرده بودند نادیده گرفته شدند تا پیامک تکراری ارسال نشود.")
        if failed_count > 0:
            msg_parts.append(f"ارسال به {failed_count} سفارش ناموفق بود.")

        full_msg = " | ".join(msg_parts) if msg_parts else "سفارشی انتخاب نشد."
        if sent_count > 0:
            self.message_user(request, full_msg, messages.SUCCESS)
        elif already_sent_count > 0:
            self.message_user(request, full_msg, messages.WARNING)
        else:
            self.message_user(request, full_msg, messages.ERROR)

    send_discount_coupon_sms_action.short_description = "ارسال پیامک کد تخفیف به سفارشات پرداخت‌نشده (پترن ۴۳۰۸۱۰)"

    def get_product_id(self, obj):
        if obj.product:
            return getattr(obj.product, 'service_id', '-')
        return "-"

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and obj.pk:
            try:
                old_obj = Order.objects.filter(pk=obj.pk).first()
                if old_obj:
                    old_status = old_obj.status
            except Exception:
                pass

        super().save_model(request, obj, form, change)

        if old_status != "4" and obj.status == "4":
            if not obj.order_finish_date:
                obj.order_finish_date = timezone.now()
                obj.save(update_fields=["order_finish_date"])
            try:
                send_order_complete(
                    phone=obj.receiver_phone,
                    orderid=obj.code,
                )
            except Exception as e:
                print(f"خطا در ارسال پیامک تکمیل سفارش: {e}")

    def save_related(self, request, form, formsets, change):
        old_refill_statuses = {r.id: r.status for r in form.instance.refill_requests.all()} if (form.instance and form.instance.pk) else {}
        super().save_related(request, form, formsets, change)
        if form.instance and form.instance.pk:
            for refill in form.instance.refill_requests.all():
                if old_refill_statuses.get(refill.id) != "completed" and refill.status == "completed":
                    if not refill.completed_at:
                        refill.completed_at = timezone.now()
                        refill.save(update_fields=["completed_at"])
                    refill.send_completion_sms()

    get_product_id.short_description = "آیدی محصول"

class FAQInline(admin.TabularInline):
    model = FAQ
    extra = 1
    fields = ('question', 'answer', 'order', 'is_active')
    ordering = ('order',)

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'product', 'order', 'is_active', 'updated_at')
    list_filter = ('is_active', 'product')
    search_fields = ('question', 'answer', 'product__name')
    list_editable = ('order', 'is_active')
    ordering = ('product', 'order')
    autocomplete_fields = ('product',)

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ["order"]
    search_fields = ["wallet_address", "private_key"]
    readonly_fields = ["wallet_address", "private_key", "public_key"]

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    readonly_fields = ['panel_balance_display']
    fieldsets = (
        (None, {
            'fields': (
                'commission_percent',
                'enable_zarinpal',
                'enable_sizpay',
                'enable_zibal',
                'enable_trx',
                'enable_card',
                'card_number',
                'card_name',
                'zarinpal_merchant_id',
                'zibal_merchant_id',
                'sizpay_merchant_id',
                'tron_wallet_address',
                'support_api_key',
                'panel_api_key',
                'sms_api_key',
                'sms_pattern_otp',
                'sms_pattern_code_user',
                'sms_pattern_code_admin',
                'sms_pattern_code_cancel',
                'sms_pattern_code_complete',
                'sms_pattern_code_refill',
                'admin_phone_number',
                'whatsapp_phone_number',
                'name',
                'domain',
                'recaptcha_site_key',
                'recaptcha_secret_key',
                'enamad',
                'telegram_page',
                'instagram_page',
                'twitter_page',
                'footer_description',
                'panel_balance_display',
            )
        }),
    )

    def panel_balance_display(self, obj):
        return f"{obj.get_panel_balance():,} دلار"
    panel_balance_display.short_description = "موجودی پنل"

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('sender', 'text', 'created_at', 'telegram_msg_id')
    can_delete = True


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_info', 'phone_or_email', 'messages_count', 'created_at', 'updated_at', 'is_closed')
    list_filter = ('is_closed', 'created_at')
    search_fields = ('id', 'name', 'phone_or_email', 'user__email', 'user__phone_number')
    ordering = ('-updated_at',)
    inlines = [ChatMessageInline]

    @admin.display(description='کاربر')
    def user_info(self, obj):
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name} ({obj.user.phone_number or obj.user.email})"
        return obj.name or 'کاربر مهمان'

    @admin.display(description='تعداد پیام‌ها')
    def messages_count(self, obj):
        return obj.messages.count()


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'sender_badge', 'text_preview', 'created_at')
    list_filter = ('sender', 'created_at')
    search_fields = ('text', 'session__id', 'session__name', 'session__phone_or_email')
    ordering = ('-created_at',)

    @admin.display(description='فرستنده')
    def sender_badge(self, obj):
        if obj.sender == ChatMessage.Sender.ADMIN:
            return format_html('<span style="background-color:#10b981;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;">پشتیبان</span>')
        return format_html('<span style="background-color:#3b82f6;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;">کاربر</span>')

    @admin.display(description='متن پیام')
    def text_preview(self, obj):
        return obj.text[:60]
