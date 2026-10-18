from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import CustomUser, IncreaseTransaction, Ticket, TicketMessage, UserPayment, PhoneOTP


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'phone_number', 'first_name', 'last_name', 'is_staff', 'is_active', 'balance')
    list_filter = ('is_staff', 'is_active')
    ordering = ('email',)
    search_fields = ('email', 'phone_number', 'first_name', 'last_name')

    fieldsets = (
        (None, {'fields': ('email', 'phone_number', 'first_name', 'last_name', 'password')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login',)}),
        (_('Extra info'), {'fields': ('balance', 'last_orders')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'phone_number', 'password1', 'password2', 'is_staff', 'is_active')}
        ),
    )


@admin.register(UserPayment)
class UserPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_id",
        "user_display",
        "user_phone",
        "amount_formatted",
        "payment_method",
        "authority",
        "status_badge",
        "created_at",
    )
    list_filter = (
        "status",
        "payment",
        "created_at",
    )
    search_fields = (
        "id",
        "authority",
        "user__email",
        "user__phone_number",
        "user__first_name",
        "user__last_name",
    )
    ordering = ("-created_at", "-id")
    readonly_fields = (
        "id",
        "created_at",
    )
    actions = ["approve_and_charge_wallet"]

    @admin.display(description="شناسه فاکتور", ordering="id")
    def invoice_id(self, obj):
        return f"WAL-{obj.id}"

    @admin.display(description="کاربر", ordering="user__email")
    def user_display(self, obj):
        if not obj.user:
            return "-"
        name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        if name:
            return f"{name} ({obj.user.email})"
        return obj.user.email

    @admin.display(description="شماره موبایل", ordering="user__phone_number")
    def user_phone(self, obj):
        return obj.user.phone_number if (obj.user and obj.user.phone_number) else "-"

    @admin.display(description="مبلغ", ordering="amount")
    def amount_formatted(self, obj):
        return "{:,} تومان".format(int(obj.amount or 0))

    @admin.display(description="درگاه پرداخت", ordering="payment")
    def payment_method(self, obj):
        return obj.get_payment_display()

    @admin.display(description="وضعیت پرداخت", ordering="status")
    def status_badge(self, obj):
        if obj.status == UserPayment.PaymentStatus.FINISHED:
            return format_html(
                '<span style="background-color:#10b981;color:#fff;padding:3px 10px;border-radius:12px;font-weight:bold;font-size:11px;">تکمیل شده</span>'
            )
        elif obj.status == UserPayment.PaymentStatus.PAYMENT:
            return format_html(
                '<span style="background-color:#f59e0b;color:#fff;padding:3px 10px;border-radius:12px;font-weight:bold;font-size:11px;">در انتظار پرداخت</span>'
            )
        return obj.get_status_display()

    @admin.action(description="تایید پرداخت دستی و افزایش موجودی کیف پول")
    def approve_and_charge_wallet(self, request, queryset):
        count = 0
        for payment in queryset:
            if payment.status == UserPayment.PaymentStatus.FINISHED:
                continue

            user = payment.user
            if user:
                user.balance = (user.balance or 0) + payment.amount
                user.save(update_fields=["balance"])

            payment.status = UserPayment.PaymentStatus.FINISHED
            payment.save(update_fields=["status"])
            count += 1

            if user and user.phone_number:
                try:
                    from social.utils import send_wallet_charge_sms
                    send_wallet_charge_sms(phone=user.phone_number, price=int(user.balance))
                except Exception as e:
                    print(f"Error sending wallet charge SMS: {e}")

        self.message_user(
            request,
            f"{count} فاکتور شارژ حساب تایید شد، به موجودی کاربر اضافه گردید و پیامک اطلاع‌رسانی ارسال شد.",
            messages.SUCCESS
        )

    def save_model(self, request, obj, form, change):
        if change:
            old_obj = UserPayment.objects.get(pk=obj.pk)
            if (old_obj.status != UserPayment.PaymentStatus.FINISHED and 
                obj.status == UserPayment.PaymentStatus.FINISHED):
                user = obj.user
                if user:
                    user.balance = (user.balance or 0) + obj.amount
                    user.save(update_fields=["balance"])
                    if user.phone_number:
                        try:
                            from social.utils import send_wallet_charge_sms
                            send_wallet_charge_sms(phone=user.phone_number, price=int(user.balance))
                        except Exception as e:
                            print(f"Error sending wallet charge SMS: {e}")
        super().save_model(request, obj, form, change)


@admin.register(PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    list_display = (
        "phone_number",
        "first_name",
        "last_name",
        "email",
        "attempts",
        "send_count",
        "is_blocked_status",
        "created_at",
        "updated_at",
    )
    list_filter = ("created_at",)
    search_fields = ("phone_number", "email", "first_name", "last_name")
    ordering = ("-created_at",)
    readonly_fields = ("phone_number", "code", "password", "created_at", "updated_at")

    @admin.display(description="مسدود موقت", boolean=True)
    def is_blocked_status(self, obj):
        return obj.is_blocked()


@admin.register(IncreaseTransaction)
class IncreaseTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "amount_int",
        "status",
        "tracking_code",
        "created_at"
    )

    list_filter = ("status", "created_at")
    search_fields = ("user__email", "tracking_code", "user__phone_number")
    ordering = ("-created_at",)
    actions = ["approve_payment"]

    @admin.action(description="تایید پرداخت و شارژ حساب")
    def approve_payment(self, request, queryset):
        count = 0
        for transaction in queryset:
            if transaction.status == IncreaseTransaction.Status.SUCCESS:
                continue

            user = transaction.user
            user.balance = (user.balance or 0) + transaction.amount
            user.save(update_fields=["balance"])

            transaction.status = IncreaseTransaction.Status.SUCCESS
            transaction.save(update_fields=["status"])
            count += 1

            try:
                from social.utils import send_wallet_charge_sms
                send_wallet_charge_sms(phone=user.phone_number, price=int(user.balance))
            except Exception as e:
                print(f"Error sending wallet charge SMS: {e}")

        self.message_user(
            request,
            f"{count} تراکنش با موفقیت تایید شد و پیامک افزایش موجودی ارسال گردید.",
            messages.SUCCESS
        )

    @admin.display(description="مبلغ", ordering="amount")
    def amount_int(self, obj):
        return "{:,} تومان".format(int(obj.amount or 0))
        
    def save_model(self, request, obj, form, change):
        if change:
            old_obj = IncreaseTransaction.objects.get(pk=obj.pk)
            if (old_obj.status != IncreaseTransaction.Status.SUCCESS and obj.status == IncreaseTransaction.Status.SUCCESS):
                user = obj.user
                user.balance = (user.balance or 0) + obj.amount
                user.save(update_fields=['balance'])
                try:
                    from social.utils import send_wallet_charge_sms
                    send_wallet_charge_sms(phone=user.phone_number, price=int(user.balance))
                except Exception as e:
                    print(f"Error sending wallet charge SMS: {e}")
        super().save_model(request, obj, form, change)


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    fields = (
        "sender",
        "message",
        "attachment",
        "created_at",
    )
    readonly_fields = ("created_at",)
    show_change_link = True


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "tracking_code",
        "title",
        "user",
        "department",
        "priority",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "priority",
        "department",
        "created_at",
    )
    search_fields = (
        "tracking_code",
        "title",
        "user__username",
        "user__email",
    )
    readonly_fields = (
        "tracking_code",
        "created_at",
        "updated_at",
        "closed_at",
    )

    inlines = [TicketMessageInline]


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = (
        "ticket",
        "sender",
        "created_at",
    )
    list_filter = (
        "created_at",
        "sender",
    )
    search_fields = (
        "ticket__tracking_code",
        "ticket__title",
        "sender__username",
        "message",
    )
    readonly_fields = ("created_at",)
