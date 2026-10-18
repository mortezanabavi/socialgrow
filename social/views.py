from django.db.models import Q
import re

def normalize_digits(s):
    if not s:
        return ""
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    arabic_digits = '٠١٢٣٤٥٦٧٨٩'
    english_digits = '0123456789'
    trans = str.maketrans(persian_digits + arabic_digits, english_digits * 2)
    return str(s).translate(trans)

def normalize_tracking_code(raw_code):
    if not raw_code:
        return ""
    clean = normalize_digits(raw_code).strip()
    clean = re.sub(r'^[#№\s]+', '', clean)
    clean = re.sub(r'^(کد|code)\s*[:\-]?\s*', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\s+', '', clean)
    return clean

def normalize_phone_number(raw_phone):
    if not raw_phone:
        return ""
    clean = normalize_digits(raw_phone).strip()
    digits = re.sub(r'\D', '', clean)
    if digits.startswith('0098') and len(digits) > 12:
        digits = '0' + digits[4:]
    elif digits.startswith('98') and len(digits) == 12:
        digits = '0' + digits[2:]
    elif digits.startswith('9') and len(digits) == 10:
        digits = '0' + digits
    return digits

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from social.models import Order, Product, SiteSettings, Wallet, NotifyRequest, DiscountCode, RefillRequest
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import OrderSerializer
import json
from .utils import verify_recaptcha, send_order_confirmation_sms, send_order_to_admin, set_order, get_usdt_price, post_to_zibal, send_refill_request_sms
from django.http import HttpResponseRedirect, JsonResponse
from django.conf import settings
import time, requests
from django.views.decorators.csrf import csrf_exempt
import random
from random import randint
from accounts.models import IncreaseTransaction, Ticket, TicketMessage, UserPayment
from django.contrib.auth.decorators import login_required
from decimal import Decimal
import jdatetime, traceback
from django.contrib import messages
from django.views.decorators.http import require_POST

def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /dashboard/",
        "Disallow: /userinfo/",
        "Disallow: /new-order/",
        "Disallow: /orders/",
        "Disallow: /tickets/",
        "Disallow: /submit-ticket/",
        "Disallow: /payment/",
        "Sitemap: https://socialgrow.ir/sitemap.xml",
        "Sitemap: https://socialgrow.ir/sitemap-products.xml",
    ]
    resp = HttpResponse("\n".join(lines), content_type="text/plain")
    resp["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    return resp
    
def einamad(request):
    lines = [
        "Hello",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

def home(request):
    pro = Product.objects.all()
    unique_products = {}
    products_list = []
    dollar_rate = get_usdt_price()
    for product in pro:
        products_list.append({
            'slug': product.slug,
            'id': product.id,
            'en': product.en,
            'name': product.name,
            'description': (product.description or '').replace('\\r\\n', '\n').replace('\\n', '\n').replace('\r\n', '\n'),
            'app': product.app,
            'toman_price': int(product.toman_price()),
            'min_order': product.min_order,
            'max_order': product.max_order
        })
    for product in pro:
        display = product.get_app_display()
        if display not in unique_products:
            unique_products[display] = product
    response = render(request, "index.html", {"products": pro, "pu": unique_products.values(), "p": json.dumps(products_list, default=str), "current_time": int(time.time()), "settings": SiteSettings.objects.first()})
    return response

def faqs(request):
    response = render(request, "faq.html", {"settings": SiteSettings.objects.first(), "current_time": int(time.time())})
    return response

def terms(request):
    response = render(request, "terms.html", {"settings": SiteSettings.objects.first(), "current_time": int(time.time())})
    return response
    
def show_products(request):
    pro = Product.objects.all()
    products_list = []
    for product in pro:
        meta_desc = product.meta_description if product.meta_description and product.meta_description.strip() not in ['بدون توضیح', ''] else (product.description or '')
        products_list.append({
            'slug': product.slug,
            'id': product.id,
            'en': product.en,
            'name': product.name,
            'description': meta_desc,
            'meta_description': meta_desc,
            'app': product.app,
            'toman_price': int(product.toman_price()),
            'price_500': int(product.get_500_price()),
            'is_premium': product.is_telegram_premium(),
            'exact_count': product.exact_count or 0,
            'min_order': product.min_order,
            'max_order': product.max_order,
            'is_available': product.is_available,
            'img': product.cover_image.url if product.cover_image else ''
        })
    response = render(request, "products.html", {"settings": SiteSettings.objects.first(), "p": json.dumps(products_list, default=str), "current_time": int(time.time())})
    return response

def log_in(request):
    response = render(request, "login.html", {"settings": SiteSettings.objects.first(), "current_time": int(time.time())})
    return response

def track_order(request):
    raw_code = request.GET.get('code')
    raw_phone = request.GET.get('phone') or request.GET.get('receiver_phone')
    if raw_code and raw_phone:
        clean_code = normalize_tracking_code(raw_code)
        clean_phone = normalize_phone_number(raw_phone)
        phone_11 = clean_phone if clean_phone.startswith('0') else ('0' + clean_phone)
        phone_10 = phone_11[1:] if phone_11.startswith('0') else phone_11
        phone_candidates = [phone_11, phone_10, '+98' + phone_10, '98' + phone_10]

        order = Order.objects.filter(
            Q(code__iexact=clean_code) | Q(code=clean_code),
            Q(receiver_phone__in=phone_candidates) | Q(receiver_phone__endswith=phone_10)
        ).select_related('product').first()
        if order:
            return render(request, "order.html", {
                "settings": SiteSettings.objects.first(),
                "current_time": int(time.time()),
                "order": order
            })

    return render(request, "track.html", {
        "settings": SiteSettings.objects.first(),
        "current_time": int(time.time()),
        "entered_code": raw_code or "",
        "entered_phone": raw_phone or ""
    })

@login_required
def payment(request):
    response = render(request, "increase.html", {"settings": SiteSettings.objects.first(), "current_time": int(time.time())})
    return response

@login_required
def card(request):
    response = render(request, "card.html", {"settings": SiteSettings.objects.first(), "current_time": int(time.time()), "amount": 500000})
    return response
    
@login_required
def dashboard(request):
    user_name = request.user.email.split('@')[0]
    orders_count = Order.objects.filter(
        receiver_phone=request.user.phone_number
    ).count()
    joined_at_shamsi = jdatetime.datetime.fromgregorian(
        datetime=request.user.joined_at
    ).strftime("%Y/%m/%d")
    response = render(request, "dashboard.html", {"settings": SiteSettings.objects.first(), "current_time": int(time.time()), "username": user_name, "count": orders_count, "balance": "{:,}".format(int(request.user.balance)), "joined_at": joined_at_shamsi})
    return response
    
@login_required
def userinfo(request):
    return render(request, "userinfo.html")

@login_required
def submit_ticket(request):
    return render(request, "submit-ticket.html")
    
@login_required
def tickets(request):
    user = request.user
    tickets = request.user.tickets.all()
    total_tickets = user.tickets.count()
    open_tickets = user.tickets.filter(status=Ticket.Status.OPEN).count()
    closed_tickets = user.tickets.filter(status=Ticket.Status.CLOSED).count()
    response = render(request, "tickets.html", {"settings": SiteSettings.objects.first(), "current_time": int(time.time()), "total_tickets": total_tickets, "open_tickets": open_tickets, "closed_tickets": closed_tickets, "tickets": tickets})
    return response
    
@login_required
def view_ticket(request, tracking_code):
    ticket = get_object_or_404(Ticket, tracking_code=tracking_code, user=request.user)
    messages = ticket.messages.select_related("sender").all()
    return render(request, "view-ticket.html", {"ticket": ticket,"messages": messages,})
    
@login_required
def post_ticket(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        priority = request.POST.get("priority", "normal")
        department = request.POST.get("department", "").strip()
        message = request.POST.get("message", "").strip()
        attachment = request.FILES.get("attachment")
        if not title or not message or not department:
            return redirect("submit_ticket")
        ticket = Ticket.objects.create(
            user=request.user,
            title=title,
            priority=priority,
            department=department
        )
        TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            message=message,
            attachment=attachment
        )
        return render(request, "submitted-ticket.html", {"tracking_code": ticket.tracking_code})
    return render(request, "submit-ticket.html")
    
@login_required
def reply_ticket(request, tracking_code):
    ticket = get_object_or_404(Ticket, tracking_code=tracking_code, user=request.user)
    if request.method == "POST":
        message = request.POST.get("message", "").strip()
        attachment = request.FILES.get("attachment")
        if not message and not attachment:
            return redirect(
                "view_ticket",
                tracking_code=tracking_code
            )
        TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            message=message,
            attachment=attachment
        )
        if ticket.status == Ticket.Status.CLOSED:
            ticket.status = Ticket.Status.OPEN
        ticket.is_read_by_admin = False
        ticket.is_read_by_user = True
        ticket.save()
    return redirect("view_ticket", tracking_code=tracking_code)


def services(request, slug):
    service = Product.objects.filter(slug=slug).first()
    if not service:
        if slug == "telegram-permium":
            alt = Product.objects.filter(slug="telegram-premium").first()
            if alt:
                return redirect("/services/telegram-premium/", permanent=True)
        elif slug == "telegram-premium":
            alt = Product.objects.filter(slug="telegram-permium").first()
            if alt:
                return redirect("/services/telegram-permium/", permanent=True)
        service = get_object_or_404(Product, slug=slug)
    faqs = service.faqs.filter(is_active=True).order_by('order')
    
    # 1. Get all available products from the same app (excluding current product)
    matching_products = list(Product.objects.filter(app=service.app, is_available=True).exclude(id=service.id))
    
    # If there are 4 or more matching products, select 4 randomly on each refresh
    if len(matching_products) >= 4:
        related_products = random.sample(matching_products, 4)
    elif len(matching_products) > 0:
        # If fewer than 4, take all matching and randomly pick from other available products
        exclude_ids = [service.id] + [p.id for p in matching_products]
        other_products = list(Product.objects.filter(is_available=True).exclude(id__in=exclude_ids))
        needed = 4 - len(matching_products)
        if len(other_products) >= needed:
            supplement = random.sample(other_products, needed)
        else:
            supplement = other_products
        related_products = matching_products + supplement
    else:
        # Fallback to random available products if no products exist in the same app
        other_products = list(Product.objects.filter(is_available=True).exclude(id=service.id))
        if len(other_products) >= 4:
            related_products = random.sample(other_products, 4)
        else:
            related_products = other_products

    # First purchase 10% discount coupon
    first_purchase_coupon = DiscountCode.objects.filter(
        is_active=True,
        value=10,
        discount_type='percent',
        user_limit=1
    ).first()

    # Calculate Order Bump complementary products (Likes/Views for IG, Reactions/Views for TG)
    bump_available = False
    bump_data = {}
    is_ig = (str(service.app) == '2' or 'instagram' in (service.en or '').lower() or 'اینستاگرام' in (service.name or ''))
    is_tg = (str(service.app) == '1' or 'telegram' in (service.en or '').lower() or 'تلگرام' in (service.name or ''))
    is_tg_group = is_tg and (
        'group' in (service.slug or '').lower() or
        'group' in (service.en or '').lower() or
        'گروه' in (service.name or '')
    )
    is_fol = service.is_follower_or_member()

    # Check refill guarantee eligibility
    has_refill_guarantee = is_fol
    if service.slug == 'telegram-real-members-with-view' or 'بدون ریزش + ویو' in (service.name or ''):
        has_refill_guarantee = False

    if is_ig and is_fol:
        bump_available = True
        like_prod = Product.objects.filter(id=6, is_available=True).first()
        if not like_prod:
            like_prod = Product.objects.filter(app='2', name__contains='لایک', is_available=True).first()
        view_prod = Product.objects.filter(id=8, is_available=True).first()
        if not view_prod:
            view_prod = Product.objects.filter(app='2', name__contains='بازدید', is_available=True).first()

        like_1k = int(like_prod.toman_price()) if like_prod else 35000
        view_1k = int(view_prod.toman_price()) if view_prod else 80000

        bump_data = {
            'bump_type': 'instagram',
            'title': 'افزودن خودکار لایک و ویو برای پست‌های اخیر',
            'desc': 'با جذب فالوور، تعامل پست‌های آخر پیجتان هم افزایش یابد تا اینستاگرام پیج شما را به اکسپلور هدایت کند.',
            'item1_name': 'لایک',
            'item1_icon': 'fa-solid fa-heart',
            'item1_color': '#ef4444',
            'item1_product_name': like_prod.name if like_prod else 'لایک پست اینستاگرام',
            'item1_unit_price': like_1k / 1000.0,
            'item1_1k_price': like_1k,
            'item2_name': 'ویو / بازدید',
            'item2_icon': 'fa-solid fa-eye',
            'item2_color': '#3b82f6',
            'item2_product_name': view_prod.name if view_prod else 'بازدید پست و ریلز اینستاگرام',
            'item2_unit_price': view_1k / 1000.0,
            'item2_1k_price': view_1k,
            'summary_label': 'مکمل (لایک و ویو):',
        }
    elif is_tg and not is_tg_group and (is_fol or service.slug == 'telegram-real-members-with-view'):
        bump_available = True
        reac_prod = Product.objects.filter(id=3, is_available=True).first()
        if not reac_prod:
            reac_prod = Product.objects.filter(app='1', name__contains='ری اکشن', is_available=True).first()
        view_prod = Product.objects.filter(id=7, is_available=True).first()
        if not view_prod:
            view_prod = Product.objects.filter(app='1', name__contains='بازدید', is_available=True).first()

        reac_1k = int(reac_prod.toman_price()) if reac_prod else 7500
        view_1k = int(view_prod.toman_price()) if view_prod else 1250

        bump_data = {
            'bump_type': 'telegram',
            'title': 'افزودن خودکار بازدید و ری‌اکشن مثبت برای پست‌های اخیر',
            'desc': 'با ورود ممبرهای جدید، بازدید و ری‌اکشن مثبت پست‌های اخیر کانال هم افزایش یابد تا تعامل و اعتبار کانال کاملاً طبیعی و واقعی باشد.',
            'item1_name': 'ری‌اکشن مثبت',
            'item1_icon': 'fa-solid fa-thumbs-up',
            'item1_color': '#10b981',
            'item1_product_name': reac_prod.name if reac_prod else 'ری‌اکشن مثبت تلگرام',
            'item1_unit_price': reac_1k / 1000.0,
            'item1_1k_price': reac_1k,
            'item2_name': 'بازدید پست',
            'item2_icon': 'fa-solid fa-eye',
            'item2_color': '#3b82f6',
            'item2_product_name': view_prod.name if view_prod else 'بازدید پست تلگرام',
            'item2_unit_price': view_1k / 1000.0,
            'item2_1k_price': view_1k,
            'summary_label': 'مکمل (بازدید و ری‌اکشن):',
        }

    sub_products = list(service.get_sub_products()) if service.has_sub_products() else []
    initial_sub_product = sub_products[0] if sub_products else service

    context = {
        "settings": SiteSettings.objects.first(),
        "current_time": int(time.time()),
        "product": service,
        "sub_products": sub_products,
        "initial_sub_product": initial_sub_product,
        "faqs": faqs,
        "related_products": related_products,
        "first_purchase_coupon": first_purchase_coupon,
        "is_follower_or_member": service.is_follower_or_member(),
        "has_refill_guarantee": has_refill_guarantee,
        "bump_available": bump_available,
        "bump_data": bump_data,
    }
    if service.is_available:
        return render(request, "service.html", context)
    else:
        return render(request, "stock.html", context)
        
@require_POST
def notify_me(request):
    product_id = request.POST.get("product")
    phone = request.POST.get("notify_phone", "").strip()
    product = get_object_or_404(Product, id=product_id)
    if not phone.isdigit() or len(phone) != 11 or not phone.startswith("09"):
        messages.error(request, "شماره تلفن وارد شده معتبر نیست.")
        return redirect("service_details", slug=product.slug)
    site_settings = SiteSettings.objects.first()
    if product.is_available:
        messages.info(request, "این سرویس هم‌اکنون موجود است، می‌توانید مستقیماً سفارش دهید.")
        return redirect("service_details", slug=product.slug)
    notify_request, created = NotifyRequest.objects.get_or_create(
        product=product,
        phone=phone,
    )
    if created:
        messages.success(request, "درخواست شما ثبت شد؛ به‌محض موجود شدن سرویس پیامک می‌شود.")
    else:
        messages.info(request, "شماره شما قبلاً برای این سرویس ثبت شده است.")
    return redirect("service_details", slug=product.slug)
    
@login_required
def orders(request):
    user = request.user
    orders = Order.objects.filter(receiver_phone=user.phone_number).exclude(status__in=[1,])
    finished = Order.objects.filter(receiver_phone=user.phone_number, status=4)
    processing = Order.objects.filter(receiver_phone=user.phone_number, status=3)
    canceled = Order.objects.filter(receiver_phone=user.phone_number, status=5)
    orders_count = orders.count()
    finished_count = finished.count()
    processing_count = processing.count()
    canceled_count = canceled.count()
    return render(request, "orders.html", {"orders": orders[::-1], "total": orders_count, "finished": finished_count, "processing": processing_count, "canceled" : canceled_count})

@login_required
def new_order(request):
    pro = Product.objects.all()
    unique_products = {}
    products_list = []
    dollar_rate = get_usdt_price()
    for product in pro:
        products_list.append({
            'id': product.id,
            'en': product.en,
            'name': product.name,
            'description': (product.description or '').replace('\\r\\n', '\n').replace('\\n', '\n').replace('\r\n', '\n'),
            'app': product.app,
            'toman_price': int(product.toman_price()),
            'min_order': product.min_order,
            'max_order': product.max_order
        })
    for product in pro:
        display = product.get_app_display()
        if display not in unique_products:
            unique_products[display] = product
    return render(request, "new-order.html", {"products": pro, "pu": unique_products.values(), "p": json.dumps(products_list, default=str), "current_time": int(time.time()), "settings": SiteSettings.objects.first()})

def inquiry(request):
    pro = Product.objects.all()
    products_list = []
    dollar_rate = get_usdt_price()
    for product in pro:
        products_list.append({
            'id': product.id,
            'en': product.en,
            'name': product.name,
            'description': (product.description or '').replace('\\r\\n', '\n').replace('\\n', '\n').replace('\r\n', '\n'),
            'app': product.app,
            'toman_price': int(product.toman_price()),
            'min_order': product.min_order,
            'max_order': product.max_order
        })
    response = render(request, "inquiry.html", {"settings": SiteSettings.objects.first(), "current_time": int(time.time()), "products": pro, "p": json.dumps(products_list, default=str)})
    return response
    
@login_required
def increaseBalance(request):
    if request.method == "POST":
        amount = request.POST.get("amount")
        method = request.POST.get("method")
        if not amount:
            return render(request, "increase.html", {
                "error": "مبلغ وارد نشده است."
            })
        try:
            amount = int(amount)
        except (ValueError, TypeError):
            return render(request, "increase.html", {
                "error": "مبلغ وارد شده معتبر نیست."
            })
        if amount < 5000:
            return render(request, "increase.html", {
                "error": "حداقل مبلغ شارژ حساب ۵,۰۰۰ تومان می‌باشد."
            })
        payment = UserPayment.objects.create(
            user=request.user,
            amount=amount,
            payment=method
        )
        res = payment.generate_payment()
        if method == 'Zibal':
            if res and payment.authority and payment.authority != "notset":
                return HttpResponseRedirect("https://gateway.zibal.ir/start/" + str(payment.authority))
            else:
                return render(request, "increase.html", {
                    "error": "خطا در اتصال به درگاه زیبال. لطفاً چند لحظه بعد مجدداً تلاش کنید."
                })
        elif method == 'Sizpay':
            if res and payment.authority and payment.authority != "notset":
                return HttpResponseRedirect("https://rt.sizpay.ir/Route/Payment?Token=" + str(payment.authority))
            else:
                return render(request, "increase.html", {
                    "error": "خطا در اتصال به درگاه سیزپی. لطفاً چند لحظه بعد مجدداً تلاش کنید."
                })
        elif method == 'Trx':
            from .utils import get_trx_price
            return render(request, "trx.html", {"settings": SiteSettings.objects.first(), "payment": payment, "wallet": payment.wallet_address, "trxprice": get_trx_price(), "trxamount": float(payment.amount/get_trx_price()), "error": ''})
        else:
            return render(request, "increase.html", {
                "error": "روش پرداخت انتخاب شده نامعتبر است."
            })
    return render(request, "increase.html")
    
@login_required
def changeinfo(request):
    if request.method == "POST":
        user = request.user
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        return redirect("userinfo")
    return redirect("userinfo")


@csrf_exempt
def validate_coupon(request):
    if request.method != 'POST':
        return JsonResponse({'valid': False, 'message': 'متد نامعتبر است.'}, status=405)
    try:
        if request.body and (request.content_type == 'application/json' or request.headers.get('Content-Type') == 'application/json'):
            try:
                data = json.loads(request.body)
            except Exception:
                data = request.POST
        else:
            data = request.POST

        raw_code = (data.get('code') or data.get('coupon_code') or '').strip().upper()
        product_id = data.get('product_id') or data.get('product')
        raw_count = data.get('count_order') or data.get('count', 1000)
        try:
            count_order = int(raw_count)
        except Exception:
            count_order = 1000
        receiver_phone = (data.get('receiver_phone') or '').strip()

        if not raw_code:
            return JsonResponse({'valid': False, 'message': 'لطفاً کد تخفیف را وارد کنید.'})

        try:
            coupon = DiscountCode.objects.get(code=raw_code)
        except DiscountCode.DoesNotExist:
            return JsonResponse({'valid': False, 'message': 'کد تخفیف وارد شده معتبر نیست یا وجود ندارد.'})

        product = None
        if product_id:
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                pass

        frontend_amount = data.get('amount')
        if frontend_amount:
            try:
                raw_price = int(frontend_amount)
            except Exception:
                raw_price = 0
        elif product:
            if product.exact_count > 0:
                raw_price = int(product.get_exact_count_price())
            elif product.en in ('data', 'charge'):
                raw_price = int(product.toman_price() * count_order)
            elif product.min_order == product.max_order:
                raw_price = int(product.toman_price())
            else:
                raw_price = int(product.toman_price() * count_order / 1000)
        else:
            try:
                raw_price = int(data.get('amount', 0))
            except Exception:
                raw_price = 0

        is_valid, msg, discount_amount = coupon.is_valid_for(
            raw_price,
            user_phone=receiver_phone,
            product=product,
            user=request.user if request.user.is_authenticated else None
        )

        if not is_valid:
            return JsonResponse({'valid': False, 'message': msg})

        final_price = max(0, raw_price - discount_amount)

        return JsonResponse({
            'valid': True,
            'code': coupon.code,
            'discount_type': coupon.discount_type,
            'discount_value': coupon.value,
            'max_discount': int(coupon.max_discount or 0),
            'min_order_amount': int(coupon.min_order_amount or 0),
            'discount_amount': discount_amount,
            'original_price': raw_price,
            'final_price': final_price,
            'formatted_discount': f'{discount_amount:,} تومان',
            'formatted_original': f'{raw_price:,} تومان',
            'formatted_final': f'{final_price:,} تومان',
            'message': f'کد تخفیف اعمال شد! ({discount_amount:,} تومان تخفیف)'
        })
    except Exception as e:
        print('Coupon Validation Error:', traceback.format_exc())
        return JsonResponse({'valid': False, 'message': 'خطا در بررسی کد تخفیف.'})

def submit_order_to_provider(order):
    """
    ثبت سفارش در پرووایدر API (justanotherpanel و ...)
    همچنین در صورت وجود پکیج مکمل Order Bump، ارسال اتوماتیک سفارش‌های لایک و ویو به پست‌های آخر
    """
    if not order or not order.product:
        return 'سفارش یا محصول نامعتبر'

    if order.product.en in ('data', 'charge'):
        oid = randint(100000000, 999999999)
        order.orderid = oid
        order.save(update_fields=['orderid'])
        return oid

    try:
        from .utils import set_order
        res = set_order(order.product.service_id, {'link': order.page_address, 'quantity': int(order.count_order)})
        if res and isinstance(res, dict) and 'order' in res:
            order.orderid = str(res['order'])
        else:
            order.orderid = 'سفارش ثبت نشده'
    except Exception as e:
        print("set_order error:", e)
        order.orderid = 'سفارش ثبت نشده'
    
    order.save(update_fields=['orderid'])

    # توجه: سفارشات مکمل Order Bump (لایک و ویو) طبق درخواست، به صورت دستی توسط مدیریت انجام می‌شود و خودکار به پرووایدر ارسال نمی‌گردد.
    return order.orderid


class SubmitOrderAPIView(APIView):
    def post(self, request):
        import traceback

        try:
            coupon_code = (request.data.get('coupon_code') or '').strip().upper()
            serializer = OrderSerializer(data=request.data)
            if serializer.is_valid():
                serializer.validated_data.pop('coupon_code', None)
                product = serializer.validated_data['product']
                # If product has sub_products or variant is submitted, resolve to specific sub-product
                sub_prod_id = request.data.get('variant_sub_product') or request.data.get('sub_product_id')
                if sub_prod_id:
                    try:
                        resolved_sub = Product.objects.get(id=int(sub_prod_id))
                        product = resolved_sub
                        serializer.validated_data['product'] = product
                    except (Product.DoesNotExist, ValueError):
                        pass
                elif product.has_sub_products():
                    first_sub = product.get_sub_products().first()
                    if first_sub:
                        product = first_sub
                        serializer.validated_data['product'] = product

                count_order = int(serializer.validated_data.get('count_order') or product.min_order or 1000)
                if product.min_order == product.max_order:
                    count_order = product.max_order
                serializer.validated_data['count_order'] = count_order

                receiver_phone = serializer.validated_data.get('receiver_phone', '')

                if product.exact_count > 0:
                    base_raw_price = int(product.get_exact_count_price())
                elif product.en in ('data', 'charge'):
                    base_raw_price = int(product.toman_price() * count_order)
                elif product.min_order == product.max_order:
                    base_raw_price = int(product.toman_price())
                else:
                    base_raw_price = int(product.toman_price() * count_order / 1000)

                # Order Bump parsing & server-side verification
                has_bump = bool(request.data.get('has_bump') in [True, 'true', '1', 1])
                bump_posts = 0
                bump_likes = 0
                bump_views = 0
                bump_price = 0
                bump_details = ""

                if has_bump:
                    try:
                        bump_posts = max(1, min(10, int(request.data.get('bump_posts_count') or 3)))
                        bump_likes = max(0, min(50000, int(request.data.get('bump_likes_each') or 0)))
                        bump_views = max(0, min(100000, int(request.data.get('bump_views_each') or 0)))

                        # Calculate accurate server-side price from Product models
                        is_tg_prod = (str(product.app) == '1' or 'telegram' in (product.en or '').lower() or 'تلگرام' in (product.name or ''))
                        is_tg_group = is_tg_prod and (
                            'group' in (product.slug or '').lower() or
                            'group' in (product.en or '').lower() or
                            'گروه' in (product.name or '')
                        )
                        if is_tg_group:
                            has_bump = False
                            bump_price = 0
                            bump_details = ""
                        elif is_tg_prod:
                            reac_prod = Product.objects.filter(id=3, is_available=True).first()
                            if not reac_prod:
                                reac_prod = Product.objects.filter(app='1', name__contains='ری اکشن', is_available=True).first()
                            view_prod = Product.objects.filter(id=7, is_available=True).first()
                            if not view_prod:
                                view_prod = Product.objects.filter(app='1', name__contains='بازدید', is_available=True).first()

                            reac_1k = int(reac_prod.toman_price()) if reac_prod else 7500
                            view_1k = int(view_prod.toman_price()) if view_prod else 1250

                            calculated_bump = int(bump_posts * ((bump_likes * reac_1k / 1000.0) + (bump_views * view_1k / 1000.0)))
                            bump_price = calculated_bump

                            parts = []
                            if bump_views > 0:
                                parts.append(f"{bump_views:,} بازدید")
                            if bump_likes > 0:
                                parts.append(f"{bump_likes:,} ری‌اکشن مثبت")
                            bump_details = f"{bump_posts} پست آخر (" + " + ".join(parts) + f") به مبلغ {bump_price:,} تومان"
                        else:
                            like_prod = Product.objects.filter(id=6, is_available=True).first()
                            if not like_prod:
                                like_prod = Product.objects.filter(app='2', name__contains='لایک', is_available=True).first()
                            view_prod = Product.objects.filter(id=8, is_available=True).first()
                            if not view_prod:
                                view_prod = Product.objects.filter(app='2', name__contains='بازدید', is_available=True).first()

                            like_1k = int(like_prod.toman_price()) if like_prod else 35000
                            view_1k = int(view_prod.toman_price()) if view_prod else 80000

                            calculated_bump = int(bump_posts * ((bump_likes * like_1k / 1000.0) + (bump_views * view_1k / 1000.0)))
                            bump_price = calculated_bump

                            parts = []
                            if bump_likes > 0:
                                parts.append(f"{bump_likes:,} لایک")
                            if bump_views > 0:
                                parts.append(f"{bump_views:,} ویو")
                            bump_details = f"{bump_posts} پست آخر (" + " + ".join(parts) + f") به مبلغ {bump_price:,} تومان"
                    except Exception as e_bp:
                        print("Bump parsing error:", e_bp)
                        has_bump = False
                        bump_price = 0

                raw_price = base_raw_price + bump_price

                coupon_obj = None
                discount_amount = 0
                if coupon_code:
                    try:
                        coupon_obj = DiscountCode.objects.get(code=coupon_code)
                        is_valid, msg, disc = coupon_obj.is_valid_for(
                            raw_price,
                            user_phone=receiver_phone,
                            product=product,
                            user=request.user if request.user.is_authenticated else None
                        )
                        if is_valid:
                            discount_amount = disc
                        else:
                            coupon_obj = None
                            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
                    except DiscountCode.DoesNotExist:
                        return Response({"error": "کد تخفیف وارد شده معتبر نیست یا وجود ندارد."}, status=status.HTTP_400_BAD_REQUEST)

                final_price = max(0, raw_price - discount_amount)

                if final_price == 0 and discount_amount > 0:
                    order = serializer.save(
                        order_full_price=0,
                        original_price=raw_price,
                        discount_amount=discount_amount,
                        coupon=coupon_obj,
                        status='3',
                        has_bump=has_bump,
                        bump_posts_count=bump_posts,
                        bump_likes_each=bump_likes,
                        bump_views_each=bump_views,
                        bump_price=bump_price,
                        bump_details=bump_details
                    )
                    if coupon_obj and order.coupon_id != coupon_obj.id:
                        order.coupon = coupon_obj
                        order.save(update_fields=['coupon'])
                    if coupon_obj:
                        try:
                            coupon_obj.used_count += 1
                            coupon_obj.save(update_fields=['used_count'])
                        except Exception: pass
                    if request.user.is_authenticated:
                        order.user = request.user
                        order.receiver_phone = request.user.phone_number
                    try:
                        send_order_confirmation_sms(order.receiver_phone, order.code)
                    except: pass
                    try:
                        send_order_to_admin(order.product.service_id, order.code)
                    except: pass
                    submit_order_to_provider(order)
                    return render(request, 'payment.html', {'result': True, 'ref_id': order.code, 'amount': 0})

                order = serializer.save(
                    order_full_price=final_price,
                    original_price=raw_price,
                    discount_amount=discount_amount,
                    coupon=coupon_obj,
                    has_bump=has_bump,
                    bump_posts_count=bump_posts,
                    bump_likes_each=bump_likes,
                    bump_views_each=bump_views,
                    bump_price=bump_price,
                    bump_details=bump_details
                )
                if coupon_obj and order.coupon_id != coupon_obj.id:
                    order.coupon = coupon_obj
                    order.save(update_fields=['coupon'])
                if order.payment_method == "zarinpal":
                    if not order.authority:
                        return Response({"error": "خطا در برقراری ارتباط با درگاه زرین‌پال. لطفاً مجدداً تلاش نمایید."}, status=status.HTTP_400_BAD_REQUEST)
                    return HttpResponseRedirect(settings.ZARINPAL_ADDRESS + str(order.authority))
                elif order.payment_method == "zibal":
                    if not order.authority:
                        return Response({"error": "خطا در برقراری ارتباط با درگاه پرداخت زیبال. لطفاً مجدداً تلاش نمایید."}, status=status.HTTP_400_BAD_REQUEST)
                    return HttpResponseRedirect("https://gateway.zibal.ir/start/" + str(order.authority))
                elif order.payment_method == "sizpay":
                    if not order.authority:
                        return Response({"error": "خطا در برقراری ارتباط با درگاه سیزپی. لطفاً مجدداً تلاش نمایید."}, status=status.HTTP_400_BAD_REQUEST)
                    html = f"""
                    <html>
                    <head><meta charset="utf-8">
                        <meta name="referrer" content="strict-origin-when-cross-origin">
                    </head>
                    <body>
                        <form id="sizpayForm" method="post" action="https://rt.sizpay.ir/Route/Payment" referrerpolicy="strict-origin-when-cross-origin">
                            <input type="hidden" name="token" value="{order.authority}" />
                        </form>
                        <script>
                            const form = document.getElementById('sizpayForm');
                            form.referrerPolicy = "strict-origin-when-cross-origin";
                            form.submit();
                        </script>
                    </body>
                    </html>
                    """
                    return HttpResponse(html)
                elif order.payment_method == "trx":
                    wallet = Wallet.objects.create(order=order)
                    wallet.generate_payment(order)
                    wallet.save()
                    return redirect("trx_payment", order_id=order.code)
                elif order.payment_method == "userbalance":
                    if not request.user.is_authenticated:
                        return Response({"error": "برای پرداخت با موجودی، لطفاً ابتدا وارد حساب خود شوید."}, status=status.HTTP_401_UNAUTHORIZED)
                    balance = request.user.balance
                    if int(balance) >= int(order.order_full_price):
                        request.user.balance -= order.order_full_price
                        request.user.save()
                        order.status = 3
                        order.user = request.user
                        order.receiver_phone = request.user.phone_number
                        if order.coupon:
                            try:
                                order.coupon.used_count += 1
                                order.coupon.save(update_fields=['used_count'])
                            except Exception: pass
                        try:
                            send_order_confirmation_sms(request.user.phone_number, order.code)
                        except: pass
                        try:
                            send_order_to_admin(order.product.service_id, order.code)
                        except: pass
                        submit_order_to_provider(order)
                        return render(request, 'payment.html', {'result': True, 'ref_id': order.code, 'amount': order.order_full_price})
                    else:
                        return render(request, "increase.html", {"error": "موجودی حساب کافی نیست."})
                else:
                    return Response({"error": "روش پرداخت نامعتبر است."}, status=status.HTTP_400_BAD_REQUEST)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            err_trace = traceback.format_exc()
            logger.error(f"SubmitOrder Error: {err_trace}")
            return Response({"error": "خطا در ثبت سفارش. لطفاً مجدداً تلاش نمایید."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FindOrderByCodeAPIView(APIView):
    def post(self, request):
        raw_code = request.data.get('code', '')
        raw_phone = request.data.get('receiver_phone', '')
        recaptcha_response = request.data.get('g-recaptcha-response')

        clean_code = normalize_tracking_code(raw_code)
        clean_phone = normalize_phone_number(raw_phone)

        if not verify_recaptcha(recaptcha_response):
            return render(request, "track.html", {
                "settings": SiteSettings.objects.first(),
                "current_time": int(time.time()),
                "errors": "کپچای امنیتی تایید نشد. لطفاً گزینه «من ربات نیستم» را تیک بزنید.",
                "entered_code": raw_code,
                "entered_phone": raw_phone
            })

        if not clean_code or not clean_phone:
            return render(request, "track.html", {
                "settings": SiteSettings.objects.first(),
                "current_time": int(time.time()),
                "errors": "لطفاً هم شماره تماس و هم کد پیگیری را به صورت کامل وارد نمایید.",
                "entered_code": raw_code,
                "entered_phone": raw_phone
            })

        phone_11 = clean_phone if clean_phone.startswith('0') else ('0' + clean_phone)
        phone_10 = phone_11[1:] if phone_11.startswith('0') else phone_11
        phone_candidates = [phone_11, phone_10, '+98' + phone_10, '98' + phone_10]

        order = Order.objects.filter(
            Q(code__iexact=clean_code) | Q(code=clean_code),
            Q(receiver_phone__in=phone_candidates) | Q(receiver_phone__endswith=phone_10)
        ).select_related('product').first()

        if order:
            return render(request, "order.html", {
                "settings": SiteSettings.objects.first(),
                "current_time": int(time.time()),
                "order": order
            })
        else:
            return render(request, "track.html", {
                "settings": SiteSettings.objects.first(),
                "current_time": int(time.time()),
                "errors": "سفارشی با این مشخصات یافت نشد. لطفاً کد پیگیری و شماره همراه را بررسی کنید.",
                "entered_code": raw_code,
                "entered_phone": raw_phone
            })
            
@login_required
def addfunds(request):
    if request.method == "POST":
        amount = request.POST.get("amount")
        method = request.POST.get("method")
        if not amount:
            return render(request, "increase.html", {
                "error": "مبلغ وارد نشده"
            })
        try:
            amount = int(amount) + randint(100, 500)
        except:
            return render(request, "increase.html", {
                "error": "مبلغ نامعتبر است"
            })
        if amount < 5000:
            return render(request, "increase.html", {
                "error": "مبلغ باید بیشتر از 5000 تومان باشد"
            })
        transaction = IncreaseTransaction.objects.create(
            user=request.user,
            amount=amount,
            status=IncreaseTransaction.Status.PENDINGP
        )
        return render(request, "card.html", {
            "amount": transaction.amount,
        })
    return render(request, "increase.html")
    
@login_required
def check_card(request):
    if request.method == "POST":
        amount_str = request.POST.get("amount")
        if not amount_str:
            return render(request, "increase.html", {
                "error": "مبلغ وارد نشده"
            })
        try:
            amount = int(amount_str)
        except ValueError:
            return render(request, "increase.html", {
                "error": "مبلغ نامعتبر است"
            })
        if amount < 5000:
            return render(request, "increase.html", {
                "error": "مبلغ باید بیشتر از 5000 تومان باشد"
            })
        transaction = IncreaseTransaction.objects.filter(
            user=request.user,
            amount=amount,
            status=IncreaseTransaction.Status.PENDINGP
        ).order_by("-created_at").first()
        if not transaction:
            return render(request, "increase.html", {
                "error": "تراکنشی در انتظار تایید با این مبلغ یافت نشد."
            })
        transaction.status = IncreaseTransaction.Status.PENDINGC
        transaction.save()
        return render(request, "waitfor.html", {
            "amount": int(transaction.amount),
        })
    return render(request, "increase.html")
            
def trx_payment(request, order_id):
    from .utils import get_trx_price
    order = get_object_or_404(Order, code=order_id)
    settings = SiteSettings.objects.first()
    wallet = Wallet.objects.filter(order=order).first()
    return render(request, "trx.html", {"settings": SiteSettings.objects.first(), "order": order, "wallet": wallet.wallet_address, "trxprice": get_trx_price(), "trxamount": float(order.order_full_price/get_trx_price()), "error": ''})
    
def paid(request, order_id):
    from .utils import get_trx_price, get_trx_balance, transfer_balance
    try:
        userpay = UserPayment.objects.get(wallet_address=order_id)
        if userpay.status == userpay.PaymentStatus.PAYMENT:
            trx_balance = get_trx_balance(userpay.wallet_address)
            if trx_balance > 0:
                fixed_amount = int(trx_balance) / 1000000
                irr_fixed = int(trx_balance) * trx_balance
                trx_amount = (int(trx_balance)-1200000)/1000000
                oramount = float(userpay.amount/trx_balance)
                oramount = oramount - (oramount * 0.05)
                settings = SiteSettings.objects.first()
                if int(irr_fixed) >= oramount:
                    transfer_balance(userpay.wallet_address, userpay.private_key, settings.tron_wallet_address)
                    userpay.user.balance = (userpay.user.balance or Decimal('0')) + Decimal(str(userpay.amount))
                    userpay.user.save(update_fields=['balance'])
                    userpay.status = userpay.PaymentStatus.FINISHED
                    userpay.save()
                    try:
                        from .utils import send_wallet_charge_sms
                        send_wallet_charge_sms(phone=userpay.user.phone_number, price=int(userpay.user.balance))
                    except Exception as e:
                        print(f"Error sending TRX wallet charge SMS: {e}")
                    return render(request, 'payment.html', {'result': True, 'is_wallet': True, 'ref_id': f"WAL-{userpay.id}", 'amount': userpay.amount})
                else:
                    return render(request, "trx.html", {"settings": SiteSettings.objects.first(), "payment": userpay, "wallet": userpay.wallet_address, "trxprice": get_trx_price(), "trxamount": float(userpay.amount/get_trx_price()), "error": 'خطا، ترونی به کیف پول شما واریز نشده.'})
            else:
                return render(request, "trx.html", {"settings": SiteSettings.objects.first(), "payment": userpay, "wallet": userpay.wallet_address, "trxprice": get_trx_price(), "trxamount": float(userpay.amount/get_trx_price()), "error": 'خطا، ترونی به کیف پول شما واریز نشده.'})
        else:
            return render(request, "trx.html", {"settings": SiteSettings.objects.first(), "payment": userpay, "wallet": userpay.wallet_address, "trxprice": get_trx_price(), "trxamount": float(userpay.amount/get_trx_price()), "error": 'خطا این فاکتور پرداخت شده میباشد.'})
    except Exception as e:
        print(traceback.format_exc())
        wallet = get_object_or_404(Wallet, wallet_address=order_id)
        order = wallet.order
        if order.status != 3:
            wallet = Wallet.objects.filter(order=order).first()
            trx_balance = get_trx_balance(wallet.wallet_address)
            if trx_balance > 0:
                fixed_amount = int(trx_balance) / 1000000
                irr_fixed = int(trx_balance) * trx_balance
                trx_amount = (int(trx_balance)-1200000)/1000000
                oramount = float(order.order_full_price/trx_balance)
                oramount = oramount - (oramount * 0.05)
                settings = SiteSettings.objects.first()
                if int(irr_fixed) >= oramount:
                    order.status = 3
                    transfer_balance(wallet.wallet_address, wallet.private_key, settings.tron_wallet_address)
                    try:
                        send_order_confirmation_sms(order.receiver_phone, order.code)
                    except: pass
                    try:
                        send_order_to_admin(order.product.service_id, order.code)
                    except: pass
                    if order.product.en != 'data' and order.product.en != 'charge':
                        try:
                            orderid = int(set_order(order.product.service_id, {'link': order.page_address, 'quantity': int(order.count_order)})['order'])
                        except Exception as e:
                            orderid = 'سفارش ثبت نشده'
                        order.orderid = orderid
                    else:
                        order.orderid = randint(100000000, 999999999)
                    order.save()
                    return render(request, 'payment.html', {'result': True, 'ref_id': order.code, 'amount': order.order_full_price})
                else:
                    return render(request, "trx.html", {"settings": SiteSettings.objects.first(), "order": order, "wallet": wallet.wallet_address, "trxprice": get_trx_price(), "trxamount": float(order.order_full_price/get_trx_price()), "error": 'خطا، ترونی به کیف پول شما واریز نشده.'})
            else:
                return render(request, "trx.html", {"settings": SiteSettings.objects.first(), "order": order, "wallet": wallet.wallet_address, "trxprice": get_trx_price(), "trxamount": float(order.order_full_price/get_trx_price()), "error": 'خطا، ترونی به کیف پول شما واریز نشده.'})
        else:
            return render(request, 'payment.html', {'result': True, 'ref_id': order.code, 'amount': order.order_full_price})

@csrf_exempt
def verify_payment(request):
    data = request.POST or request.GET
    authority = data.get('Authority') or data.get('Token') or data.get('trackId')
    status = request.GET.get('Status') or 'OK'

    if not authority:
        return render(request, 'fail.html', {
            'result': False,
            'current_time': int(time.time()),
            'ref_id': int(time.time()),
            'message': 'شناسه پرداخت نامعتبر یا دریافت نشد.'
        })

    order = Order.objects.filter(authority=authority).first()
    user_pay = None
    if not order:
        user_pay = UserPayment.objects.filter(authority=authority).first()

    if not order and not user_pay:
        return render(request, 'fail.html', {
            'result': False,
            'current_time': int(time.time()),
            'ref_id': authority,
            'message': 'سفارش یا صورت‌حسابی با این شناسه یافت نشد.'
        })

    sgd = SiteSettings.objects.first()

    # ----------------------------------------------------
    # Case 1: Wallet Top-Up (UserPayment)
    # ----------------------------------------------------
    if user_pay:
        if user_pay.status == UserPayment.PaymentStatus.FINISHED:
            return render(request, 'payment.html', {
                'result': True,
                'is_wallet': True,
                'current_time': int(time.time()),
                'ref_id': f"WAL-{user_pay.id}",
                'amount': user_pay.amount
            })

        if status == 'NOK':
            return render(request, 'fail.html', {
                'result': False,
                'is_wallet': True,
                'current_time': int(time.time()),
                'ref_id': f"WAL-{user_pay.id}",
                'message': 'پرداخت توسط کاربر لغو شد.'
            })

        if user_pay.payment == UserPayment.PaymentType.ZIBAL or user_pay.payment == 'Zibal':
            success = request.GET.get('success') or request.POST.get('success') or 2
            if str(success) == '1':
                merchant_id = sgd.zibal_merchant_id if (sgd and sgd.zibal_merchant_id not in ['notset', '', None]) else getattr(settings, 'ZIBAL_MERCHANT', 'zibal')
                parameters = {
                    "merchant": merchant_id,
                    "trackId": authority
                }
                try:
                    result = post_to_zibal(parameters)
                    res_code = int(result.get('result', 0))
                except Exception as e:
                    res_code = 0
                    result = {'message': str(e)}

                if res_code in [100, 201]:
                    if user_pay.status != UserPayment.PaymentStatus.FINISHED:
                        user = user_pay.user
                        current_bal = Decimal(str(user.balance or 0))
                        user.balance = current_bal + Decimal(str(user_pay.amount))
                        user.save(update_fields=['balance'])
                        user_pay.status = UserPayment.PaymentStatus.FINISHED
                        user_pay.save(update_fields=['status'])
                        try:
                            from .utils import send_wallet_charge_sms
                            send_wallet_charge_sms(phone=user.phone_number, price=int(user.balance))
                        except Exception as e:
                            print(f"Error sending wallet charge SMS: {e}")
                    return render(request, 'payment.html', {
                        'result': True,
                        'is_wallet': True,
                        'current_time': int(time.time()),
                        'ref_id': f"WAL-{user_pay.id}",
                        'amount': user_pay.amount
                    })
                else:
                    msg = result.get('message', 'پرداخت ناموفق، تراکنش تأیید نشد.')
                    return render(request, 'fail.html', {
                        'result': False,
                        'is_wallet': True,
                        'current_time': int(time.time()),
                        'ref_id': f"WAL-{user_pay.id}",
                        'message': f'خطا: {msg}'
                    })
            else:
                return render(request, 'fail.html', {
                    'result': False,
                    'is_wallet': True,
                    'current_time': int(time.time()),
                    'ref_id': f"WAL-{user_pay.id}",
                    'message': 'پرداخت توسط کاربر لغو شد یا ناموفق بود.'
                })

        elif user_pay.payment == UserPayment.PaymentType.SIZPAY or user_pay.payment == 'Sizpay':
            ResCod = str(data.get('ResCod')) or "1035"
            if ResCod in ["0", "00"]:
                url = "https://rt.sizpay.ir/api/PaymentSimple/ConfirmSimple"
                c_data = {
                    "sizPayKey": sgd.sizpay_merchant_id if sgd else "",
                    "Token": authority,
                    "amount": user_pay.amount * 10
                }
                headers = {
                    "User-Agent": "Sizpay Rest Api v1",
                    "Content-Type": "application/json"
                }
                try:
                    response = requests.post(url, data=json.dumps(c_data), headers=headers, timeout=15)
                    r_json = response.json()
                    if str(r_json.get("ResCod")) in ["0", "00"]:
                        if user_pay.status != UserPayment.PaymentStatus.FINISHED:
                            user = user_pay.user
                            current_bal = Decimal(str(user.balance or 0))
                            user.balance = current_bal + Decimal(str(user_pay.amount))
                            user.save(update_fields=['balance'])
                            user_pay.status = UserPayment.PaymentStatus.FINISHED
                            user_pay.save(update_fields=['status'])
                            try:
                                from .utils import send_wallet_charge_sms
                                send_wallet_charge_sms(phone=user.phone_number, price=int(user.balance))
                            except Exception as e:
                                print(f"Error sending wallet charge SMS: {e}")
                        return render(request, 'payment.html', {
                            'result': True,
                            'is_wallet': True,
                            'current_time': int(time.time()),
                            'ref_id': f"WAL-{user_pay.id}",
                            'amount': user_pay.amount
                        })
                except Exception:
                    pass
            return render(request, 'fail.html', {
                'result': False,
                'is_wallet': True,
                'current_time': int(time.time()),
                'ref_id': f"WAL-{user_pay.id}",
                'message': 'پرداخت با درگاه سیزپی تأیید نشد.'
            })
        else:
            return render(request, 'fail.html', {
                'result': False,
                'is_wallet': True,
                'current_time': int(time.time()),
                'ref_id': f"WAL-{user_pay.id}",
                'message': 'روش پرداخت معتبر نیست.'
            })

    # ----------------------------------------------------
    # Case 2: Product Order (Order)
    # ----------------------------------------------------
    if order.status == 3:
        return render(request, 'payment.html', {
            'result': True,
            'current_time': int(time.time()),
            'ref_id': order.code,
            'amount': order.order_full_price
        })

    if status == 'NOK':
        return render(request, 'fail.html', {
            'result': False,
            'current_time': int(time.time()),
            'ref_id': order.code,
            'message': 'پرداخت توسط کاربر لغو شد.'
        })

    if order.payment_method == "zarinpal":
        data = {
            "merchant_id": sgd.zarinpal_merchant_id,
            "amount": order.order_full_price * 10,
            "authority": authority
        }
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        try:
            response = requests.post(settings.ZARINPAL_API_VERIFY, data=json.dumps(data), headers=headers, timeout=10)
            if response.status_code in [200, 401]:
                res_data = response.json()
                try:
                    if res_data['data']['code'] in [100, 101]:
                        order.status = 3
                        if order.coupon:
                            try:
                                order.coupon.used_count += 1
                                order.coupon.save(update_fields=['used_count'])
                            except Exception: pass
                        try:
                            send_order_confirmation_sms(order.receiver_phone, order.code)
                        except: pass
                        try:
                            send_order_to_admin(order.product.service_id, order.code)
                        except: pass
                        submit_order_to_provider(order)
                        return render(request, 'payment.html', {'result': True, "current_time": int(time.time()), 'ref_id': order.code, 'amount': order.order_full_price})
                    else:
                        return render(request, 'fail.html', {'result': False, "current_time": int(time.time()), 'ref_id': order.code, 'message': 'کد {}'.format(res_data['errors']['message'])})
                except:
                    return render(request, 'fail.html', {'result': False, "current_time": int(time.time()), 'ref_id': order.code, 'message': 'کد {}'.format(res_data['errors']['code'])})
            else:
                return render(request, 'fail.html', {'result': False, "current_time": int(time.time()), 'ref_id': order.code, 'message': 'عدم اتصال به درگاه'})
        except requests.exceptions.RequestException:
            return render(request, 'fail.html', {'result': False, "current_time": int(time.time()), 'ref_id': order.code, 'message': 'خطا در ارتباط با سرور زرین‌پال'})

    elif order.payment_method == 'zibal':
        success = request.GET.get('success') or request.POST.get('success') or 2
        if int(success) == 1:
            merchant_id = sgd.zibal_merchant_id if (sgd and sgd.zibal_merchant_id not in ['notset', '', None]) else getattr(settings, 'ZIBAL_MERCHANT', 'zibal')
            parameters = {
                "merchant": merchant_id,
                "trackId": authority
            }
            try:
                result = post_to_zibal(parameters)
                res_code = int(result.get('result', 0))
            except Exception as e:
                res_code = 0
                result = {'message': str(e)}

            if res_code in [100, 201]:
                if request.user.is_authenticated:
                    order.user = request.user
                    order.receiver_phone = request.user.phone_number
                    order.save()
                order.status = 3
                if order.coupon:
                    try:
                        order.coupon.used_count += 1
                        order.coupon.save(update_fields=['used_count'])
                    except Exception: pass
                try:
                    send_order_confirmation_sms(order.receiver_phone, order.code)
                except: pass
                try:
                    send_order_to_admin(order.product.service_id, order.code)
                except: pass
                if order.product.en != 'data' and order.product.en != 'charge':
                    try:
                        orderid = int(set_order(order.product.service_id, {'link': order.page_address, 'quantity': int(order.count_order)})['order'])
                    except Exception as e:
                        orderid = 'سفارش ثبت نشده'
                    order.orderid = orderid
                else:
                    order.orderid = randint(100000000, 999999999)
                order.save()
                return render(request, 'payment.html', {'result': True, "current_time": int(time.time()), 'ref_id': order.code, 'amount': order.order_full_price})
            else:
                msg = result.get('message', 'پرداخت ناموفق، تراکنش تأیید نشد.')
                return render(request, 'fail.html', {'result': False, "current_time": int(time.time()), 'ref_id': order.code, 'message': f'خطا: {msg}'})
        else:
            return render(request, 'fail.html', {'result': False, "current_time": int(time.time()), 'ref_id': order.code, 'message': 'پرداخت ناموفق، تراکنش لغو شد.'})

    elif order.payment_method == "sizpay":
        ResCod = str(data.get('ResCod')) or "1035"
        if ResCod in ["0", "00"]:
            url = "https://rt.sizpay.ir/api/PaymentSimple/ConfirmSimple"
            data = {
                "sizPayKey": sgd.sizpay_merchant_id,
                "Token": authority,
                "amount": order.order_full_price * 10
            }
            headers = {
                "User-Agent": "Sizpay Rest Api v1",
                "Content-Type": "application/json"
            }
            try:
                response = requests.post(url, data=json.dumps(data), headers=headers, timeout=15)
                result = response.json()

                if str(result.get("ResCod")) in ["0", "00"]:
                    order.status = 3
                    try:
                        send_order_confirmation_sms(order.receiver_phone, order.code)
                    except: pass
                    try:
                        send_order_to_admin(order.product.service_id, order.code)
                    except: pass
                    if order.product.en != 'data' and order.product.en != 'charge':
                        try:
                            orderid = int(set_order(order.product.service_id, {'link': order.page_address, 'quantity': int(order.count_order)})['order'])
                        except Exception as e:
                            orderid = 'سفارش ثبت نشده'
                        order.orderid = orderid
                    else:
                        order.orderid = randint(100000000, 999999999)
                    order.save()
                    return render(request, 'payment.html', {'result': True, "current_time": int(time.time()), 'ref_id': order.code, 'amount': order.order_full_price})
                else:
                    return render(request, 'fail.html', {'result': False, "current_time": int(time.time()), 'ref_id': order.code, 'message': 'پرداخت ناموفق، تراکنش لغو شد.'})

            except requests.exceptions.RequestException as e:
                return render(request, 'fail.html', {'result': False, "current_time": int(time.time()), 'ref_id': order.code, 'message': 'خطا در ارتباط با سیزپی.'})

        else:
            return render(request, 'fail.html', {'result': False, "current_time": int(time.time()), 'ref_id': order.code, 'message': 'پرداخت ناموفق، تراکنش لغو شد.'})

@csrf_exempt
@require_POST
def request_refill(request):
    """
    ثبت درخواست جبران ریزش برای سفارش‌های فالوور یا ممبر پس از گذشت ۱ روز
    """
    try:
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        except Exception:
            data = request.POST

        code = (data.get('code') or data.get('order_code') or '').strip()
        phone = (data.get('phone') or data.get('receiver_phone') or '').strip()
        user_desc = (data.get('description') or data.get('user_description') or '').strip()

        if not code:
            return JsonResponse({'success': False, 'message': 'کد پیگیری سفارش الزامی است.'}, status=400)

        clean_code = normalize_tracking_code(code)
        clean_phone = normalize_phone_number(phone) if phone else ''

        query = Q(code__iexact=clean_code) | Q(code=clean_code)
        if clean_phone:
            phone_11 = clean_phone if clean_phone.startswith('0') else ('0' + clean_phone)
            phone_10 = phone_11[1:] if phone_11.startswith('0') else phone_11
            phone_candidates = [phone_11, phone_10, '+98' + phone_10, '98' + phone_10]
            query &= (Q(receiver_phone__in=phone_candidates) | Q(receiver_phone__endswith=phone_10))

        order = Order.objects.filter(query).select_related('product').first()
        if not order:
            return JsonResponse({'success': False, 'message': 'سفارش با مشخصات وارد شده یافت نشد.'}, status=404)

        if not order.is_refill_eligible_product():
            return JsonResponse({
                'success': False,
                'message': 'این سرویس شامل ضمانت جبران ریزش نمی‌باشد یا وضعیت سفارش هنوز تأیید/تکمیل نشده است.'
            }, status=400)

        if not order.can_request_refill():
            rem_text = order.refill_unlock_remaining_hours_text()
            return JsonResponse({
                'success': False,
                'message': f'امکان ثبت درخواست جبران ریزش ۲۴ ساعت پس از ثبت سفارش فعال می‌شود ({rem_text}).'
            }, status=400)

        # بررسی درخواست فعال در جریان
        existing_active = order.refill_requests.filter(status__in=['pending', 'processing']).first()
        if existing_active:
            return JsonResponse({
                'success': False,
                'message': 'درخواست جبران ریزش برای این سفارش قبلاً ثبت شده و در حال بررسی است.'
            }, status=400)

        refill = RefillRequest.objects.create(
            order=order,
            user_phone=order.receiver_phone,
            page_address=order.page_address,
            product_name=order.product.name,
            count_order=order.count_order,
            user_description=user_desc or None,
            status='pending'
        )

        # ارسال پیامک تایید ثبت درخواست جبران ریزش به کاربر
        try:
            send_refill_request_sms(order.receiver_phone, order.code)
        except Exception as e:
            print(f"Error sending refill request SMS: {e}")

        return JsonResponse({
            'success': True,
            'message': 'درخواست جبران ریزش شما با موفقیت ثبت شد و به پنل مدیریت ارسال گردید.',
            'status': refill.status,
            'status_title': refill.get_status_display(),
            'created_at': refill.get_created_date()
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'خطا در ثبت درخواست: {str(e)}'}, status=500)
def recent_orders_api(request):
    from django.http import JsonResponse
    import random
    from django.utils import timezone
    try:
        orders = Order.objects.exclude(status='1').select_related('product').order_by('-id')[:25]
        data = []
        now = timezone.now()
        cities = ['تهران', 'مشهد', 'اصفهان', 'شیراز', 'تبریز', 'کرج', 'اهواز', 'قم', 'رشت', 'ساری', 'یزد', 'کرمان', 'همدان', 'کیش', 'گرگان', 'قزوین']
        for idx, o in enumerate(orders):
            p = o.receiver_phone or ''
            # Mask middle digits: 0912***4567
            if len(p) >= 10:
                masked = p[:4] + '***' + p[-4:]
            else:
                masked = '09' + str(random.randint(10, 39)) + '***' + str(random.randint(1000, 9999))
            
            p_name = o.product.name if o.product else 'خدمات شبکه‌های اجتماعی'
            # Format count
            count_val = o.count_order
            if count_val and count_val > 0:
                count_str = f"{count_val:,} عدد"
            else:
                count_str = "۱ پکیج"

            # Calculate relative time in Persian
            if o.order_date:
                diff = (now - o.order_date).total_seconds()
                if diff < 120:
                    time_ago = 'همین الان'
                elif diff < 3600:
                    time_ago = f"{max(2, int(diff // 60))} دقیقه پیش"
                elif diff < 86400:
                    time_ago = f"{int(diff // 3600)} ساعت پیش"
                else:
                    time_ago = f"{int(diff // 86400)} روز پیش"
            else:
                time_ago = f"{(idx * 3) + 2} دقیقه پیش"

            city = cities[o.id % len(cities)]
            
            # Determine platform icon class
            icon = 'instagram'
            if 'تلگرام' in p_name or 'telegram' in p_name.lower():
                icon = 'telegram'
            elif 'یوتیوب' in p_name:
                icon = 'youtube'
            elif 'تیک تاک' in p_name:
                icon = 'tiktok'
            
            data.append({
                'phone': masked,
                'product': p_name,
                'count': count_str,
                'city': city,
                'time_ago': time_ago,
                'icon': icon,
                'id': o.id
            })
        return JsonResponse({'status': 'ok', 'orders': data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'msg': str(e)})


# ================= CHAT ONLINE & TELEGRAM INTEGRATION =================
import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from social.models import ChatSession, ChatMessage
from social.chat_telegram_service import (
    notify_admin_new_user_message,
    send_telegram_message,
    TELEGRAM_ADMIN_CHAT_ID
)

logger = logging.getLogger(__name__)


def _get_or_create_session(request):
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key

    session = ChatSession.objects.filter(session_key=session_key).first()
    if not session:
        user = request.user if request.user.is_authenticated else None
        name = ""
        phone = ""
        if user:
            name = f"{user.first_name} {user.last_name}".strip()
            phone = user.phone_number or user.email

        session = ChatSession.objects.create(
            session_key=session_key,
            user=user,
            name=name,
            phone_or_email=phone
        )
    else:
        # If user recently logged in, link user
        if not session.user and request.user.is_authenticated:
            session.user = request.user
            if not session.name:
                session.name = f"{request.user.first_name} {request.user.last_name}".strip()
            if not session.phone_or_email:
                session.phone_or_email = request.user.phone_number or request.user.email
            session.save(update_fields=["user", "name", "phone_or_email"])

    return session


@require_http_methods(["GET"])
def chat_init(request):
    """
    Initializes or retrieves the active chat session for the visitor.
    """
    session = _get_or_create_session(request)
    messages = session.messages.order_by("created_at")

    msg_list = []
    for m in messages:
        msg_list.append({
            "id": m.id,
            "sender": m.sender,
            "text": m.text,
            "is_read": bool(m.is_read),
            "created_at": m.created_at.strftime("%H:%M"),
        })

    unread_count = session.messages.filter(sender=ChatMessage.Sender.ADMIN, is_read=False).count()

    return JsonResponse({
        "status": "success",
        "session_id": session.id,
        "name": session.name,
        "phone_or_email": session.phone_or_email,
        "is_authenticated": request.user.is_authenticated,
        "unread_count": unread_count,
        "messages": msg_list,
    })


@require_http_methods(["POST"])
@csrf_exempt
def chat_send_message(request):
    """
    Receives a message from the site visitor and notifies Telegram admin.
    """
    session = _get_or_create_session(request)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        data = request.POST

    text = str(data.get("text", "")).strip()
    name = str(data.get("name", "")).strip()
    phone_or_email = str(data.get("phone_or_email", "")).strip()

    if not text:
        return JsonResponse({"status": "error", "message": "متن پیام خالی است."}, status=400)

    # Update contact info if provided
    update_fields = []
    if name and session.name != name:
        session.name = name
        update_fields.append("name")
    if phone_or_email and session.phone_or_email != phone_or_email:
        session.phone_or_email = phone_or_email
        update_fields.append("phone_or_email")
    if update_fields:
        session.save(update_fields=update_fields)

    # Create message
    msg = ChatMessage.objects.create(
        session=session,
        sender=ChatMessage.Sender.USER,
        text=text
    )

    # Notify Telegram admin asynchronously/safely
    try:
        notify_admin_new_user_message(session, msg)
    except Exception as e:
        logger.error(f"Error notifying admin via Telegram: {e}")

    return JsonResponse({
        "status": "success",
        "message": {
            "id": msg.id,
            "sender": msg.sender,
            "text": msg.text,
            "created_at": msg.created_at.strftime("%H:%M"),
        }
    })


@require_http_methods(["GET"])
def chat_poll_messages(request):
    """
    Polls for new messages received after last_id.
    """
    session = _get_or_create_session(request)
    last_id = request.GET.get("last_id", 0)
    try:
        last_id = int(last_id)
    except ValueError:
        last_id = 0

    is_open = request.GET.get("is_open") in ["1", "true", "True"]

    new_messages = session.messages.filter(id__gt=last_id).order_by("created_at")

    msg_list = []
    for m in new_messages:
        # Mark admin messages as read only when chat is actively open
        if is_open and m.sender == ChatMessage.Sender.ADMIN and not m.is_read:
            m.is_read = True
            m.save(update_fields=["is_read"])

        msg_list.append({
            "id": m.id,
            "sender": m.sender,
            "text": m.text,
            "is_read": bool(m.is_read),
            "created_at": m.created_at.strftime("%H:%M"),
        })

    return JsonResponse({
        "status": "success",
        "messages": msg_list,
    })


@csrf_exempt
@require_http_methods(["POST"])
def chat_mark_read(request):
    """
    Marks all unread admin messages as read in the active visitor session.
    """
    session = _get_or_create_session(request)
    session.messages.filter(sender=ChatMessage.Sender.ADMIN, is_read=False).update(is_read=True)
    return JsonResponse({"status": "success"})


@csrf_exempt
@require_http_methods(["POST"])
def telegram_webhook(request):
    """
    Receives Telegram webhook updates when admin replies or sends a message.
    """
    try:
        update = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Telegram webhook JSON parse error: {e}")
        return HttpResponse("OK")

    msg = update.get("message")
    if not msg:
        return HttpResponse("OK")

    from_user = msg.get("from", {})
    from_id = from_user.get("id")
    text = msg.get("text", "").strip()

    # Verify message is from the authorized admin
    if from_id != TELEGRAM_ADMIN_CHAT_ID:
        return HttpResponse("OK")

    # If it's a command like /start
    if text == "/start":
        send_telegram_message(
            "👋 <b>سلام مدیر گرامی سوشال گرو!</b>\n\n"
            "ربات چت آنلاین با موفقیت متصل است.\n"
            "هر پیامی از سمت کاربران سایت در این چت برای شما ارسال خواهد شد و با <b>Reply</b> کردن روی هر پیام، پاسخ شما مستقیماً در پنجره چت آنلاین سایت به کاربر نمایش داده می‌شود."
        )
        return HttpResponse("OK")

    reply_to = msg.get("reply_to_message")
    session = None

    if reply_to:
        reply_tg_msg_id = reply_to.get("message_id")
        # Find session either by user message with this telegram_msg_id or telegram_thread_msg_id
        user_msg = ChatMessage.objects.filter(telegram_msg_id=reply_tg_msg_id).first()
        if user_msg:
            session = user_msg.session
        else:
            session = ChatSession.objects.filter(telegram_thread_msg_id=reply_tg_msg_id).first()

    # If not a reply, try to find the latest active session
    if not session:
        # Try to parse session id from text if admin typed e.g. #123 سلام
        import re
        match = re.match(r"^#?(\d+)\s+(.+)$", text, re.DOTALL)
        if match:
            s_id, actual_text = match.groups()
            session = ChatSession.objects.filter(id=int(s_id)).first()
            if session:
                text = actual_text

    if not session:
        # Fallback to the latest active session with messages in last 24h
        session = ChatSession.objects.filter(is_closed=False).order_by("-updated_at").first()

    if session and text:
        ChatMessage.objects.create(
            session=session,
            sender=ChatMessage.Sender.ADMIN,
            text=text
        )
        session.updated_at = timezone.now()
        session.save(update_fields=["updated_at"])

        # Send confirmation to admin
        send_telegram_message(
            f"✅ <i>پاسخ شما با موفقیت برای کاربر در چت #{session.id} ارسال شد.</i>",
            reply_to_message_id=msg.get("message_id")
        )
    else:
        send_telegram_message(
            "⚠️ <i>گفتگوی مربوط به این پیام پیدا نشد. لطفاً روی پیام کاربر Reply کنید یا شناسه گفتگو را در ابتدای پیام بنویسید (مثال: #12 سلام).</i>",
            reply_to_message_id=msg.get("message_id")
        )

    return HttpResponse("OK")
