import requests, math, re
from sms_ir import SmsIr
from .models import SiteSettings
from django.core.cache import cache
try:
    from tronapi import Tron
except ImportError:
    Tron = None
from ippanel import Client as IPClient
from random import randint
from bs4 import BeautifulSoup, NavigableString


BLOCK_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'blockquote', 'div', 'table', 'p', 'br'}
def clean_content(html):
    soup = BeautifulSoup(html, 'lxml')
    changed = True
    while changed:
        changed = False
        for p in soup.find_all('p'):
            children = [c for c in p.children if not (isinstance(c, NavigableString) and not c.strip())]
            if len(children) == 1 and getattr(children[0], 'name', None) in BLOCK_TAGS:
                p.replace_with(children[0])
                changed = True
                break
            elif any(getattr(c, 'name', None) in BLOCK_TAGS for c in children):
                p.unwrap()
                changed = True
                break
    for p in soup.find_all('p'):
        if not p.get_text(strip=True) and not p.find(['img', 'br']):
            p.decompose()
    body = soup.find('body')
    if body:
        return ''.join(str(c) for c in body.contents).strip()
    return str(soup).strip()

def get_site_settings():
    try:
        st = SiteSettings.objects.first()
        if not st:
            st = SiteSettings.objects.create(
                name="سوشال گرو",
                domain="localhost:8000",
                admin_phone_number="notset",
                whatsapp_phone_number="notset",
                card_number="6037990000000000",
                card_name="پیش‌فرض",
                recaptcha_site_key="",
                recaptcha_secret_key="",
                panel_api_key="notset",
                sms_api_key="notset",
                support_api_key="notset"
            )
        return st
    except Exception:
        return None
    
def generate_trx_wallet():
    full_node = 'https://api.trongrid.io'
    solidity_node = 'https://api.trongrid.io'
    event_server = 'https://api.trongrid.io'

    tron = Tron(full_node=full_node,
            solidity_node=solidity_node,
            event_server=event_server)

    account = tron.create_account
    address = account.address.base58
    key = account.private_key
    
    return address, key, address

def get_trx_balance(address):
    full_node = "https://api.trongrid.io"
    solidity_node = "https://api.trongrid.io"
    event_server = "https://api.trongrid.io"
    
    tron = Tron(full_node=full_node,
            solidity_node=solidity_node,
            event_server=event_server)
            
    balance = tron.trx.get_balance(address)
    return balance
    
def transfer_balance(address, key, oaddress):
    full_node = "https://api.trongrid.io"
    solidity_node = "https://api.trongrid.io"
    event_server = "https://api.trongrid.io"
    
    tron = Tron(full_node=full_node,
            solidity_node=solidity_node,
            event_server=event_server)
            
    balance = tron.trx.get_balance(address)
    trx_amount = (int(balance)-1200000)/1000000
    
    tron.private_key = key
    tron.default_address = address
    
    try:
        tron.trx.send_transaction(oaddress, trx_amount)
        return True
    except: return False
    
def get_usdt_price():
    cached_price = cache.get("usdt_price")
    if cached_price is not None:
        return cached_price
    try:
        result = requests.get('https://api.wallex.ir/v1/markets', timeout=5).json()['result']['symbols']['USDTTMN']['stats']
        last_price = float(result['lastPrice'])
        rounded_price = round(last_price / 5000) * 5000
        cache.set("usdt_price", int(rounded_price), timeout=86400)
        return int(rounded_price)
    except Exception as e:
        print(e)
        return 270000
    
def get_trx_price():
    cached_price = cache.get("trx_price")
    if cached_price is not None:
        return cached_price
    try:
        result = requests.get('https://api.wallex.ir/v1/markets', timeout=5).json()['result']['symbols']['TRXTMN']['stats']
        last_price = float(result['lastPrice'])
        rounded_price = round(last_price / 2000) * 2000
        cache.set("trx_price", int(rounded_price), timeout=86400)
        return int(rounded_price)
    except Exception as e:
        print(e)
        return 86000

def verify_recaptcha(token):
    from django.conf import settings as django_settings
    st = get_site_settings()
    secret_key = (st.recaptcha_secret_key if st and st.recaptcha_secret_key else None) or getattr(django_settings, 'RECAPTCHA_SECRET_KEY', None)
    if not secret_key or str(secret_key).strip().lower() in ["notset", "", "none"]:
        return True
    if not token:
        return False
    url = "https://www.google.com/recaptcha/api/siteverify"
    data = {
        'secret': secret_key,
        'response': token
    }
    try:
        response = requests.post(url, data=data, timeout=5)
        result = response.json()
        return result.get("success", False)
    except Exception:
        return True

def send_order_confirmation_sms(phone, *args, **kwargs):
    settings = get_site_settings()
    if not settings or not settings.sms_api_key or settings.sms_api_key == "notset":
        return False
    template_id = settings.sms_pattern_code_user
    if not template_id or template_id == "notset":
        return False
    if kwargs.get('orderid'):
        orderid = kwargs.get('orderid')
    elif len(args) == 1:
        orderid = args[0]
    elif len(args) >= 2:
        orderid = args[1]
    else:
        orderid = ""
    try:
        sms_ir = SmsIr(settings.sms_api_key)
        sms_ir.send_verify_code(
            number=str(phone).strip(),
            template_id=template_id,
            parameters=[{
                "name" : "ORDERID",
                "value": str(orderid),
            }],
        )
        return True
    except Exception as e:
        print(f"Error in send_order_confirmation_sms: {e}")
        return False
    
def SendOTP(phone, otpcode=None):
    from django.conf import settings as django_settings
    if otpcode is None:
        otpcode = randint(100000, 999999)
    settings = get_site_settings()
    sms_key = (settings.sms_api_key if settings and settings.sms_api_key else None) or getattr(django_settings, 'SMS_API_KEY', None)
    if not sms_key or str(sms_key).strip().lower() in ["notset", "", "none"]:
        print(f"\n{'='*50}\n🔑 [DEV/TEST MODE] OTP Code for {phone}: {otpcode}\n{'='*50}\n")
        return True
    try:
        sms_ir = SmsIr(sms_key)
        template_id = getattr(settings, 'sms_pattern_otp', None) or getattr(django_settings, 'TEMPLATE_ID', 559599)
        sms_ir.send_verify_code(
            number=str(phone).strip(),
            template_id=template_id,
            parameters=[
                {
                    "name" : "CODE",
                    "value": str(otpcode),
                }
            ],
        )
        return True
    except Exception as e:
        print(f"Error in SendOTP: {e} -> Fallback OTP for {phone}: {otpcode}")
        return True

def send_order_to_admin(item, orderid):
    settings = get_site_settings()
    if not settings or not settings.sms_api_key or settings.sms_api_key == "notset":
        return False
    template_id = settings.sms_pattern_code_admin
    if not template_id or template_id == "notset":
        return False
    admin_phone = str(settings.admin_phone_number).strip()
    if not admin_phone or admin_phone == "notset":
        return False
    try:
        sms_ir = SmsIr(settings.sms_api_key)
        sms_ir.send_verify_code(
            number=admin_phone,
            template_id=template_id,
            parameters=[{
                    "name" : "ITEMS",
                    "value": str(item),
                },
                {
                    "name" : "ORDERID",
                    "value": str(orderid),
                },
            ],
        )
        return True
    except Exception as e:
        print(f"Error in send_order_to_admin: {e}")
        return False
    
def send_order_complete(phone, orderid=None, code=None, **kwargs):
    final_id = orderid or code or kwargs.get('order_id') or ""
    settings = get_site_settings()
    if not settings or not settings.sms_api_key or settings.sms_api_key == "notset":
        return False
    template_id = settings.sms_pattern_code_complete
    if not template_id or template_id == "notset":
        return False
    try:
        sms_ir = SmsIr(settings.sms_api_key)
        sms_ir.send_verify_code(
            number=str(phone).strip(),
            template_id=template_id,
            parameters=[{
                "name" : "ORDERID",
                "value": str(final_id),
            }],
        )
        return True
    except Exception as e:
        print(f"Error in send_order_complete: {e}")
        return False
    
def send_order_cancel(phone, orderid):
    settings = get_site_settings()
    if not settings or not settings.sms_api_key or settings.sms_api_key == "notset":
        return False
    template_id = settings.sms_pattern_code_cancel
    if not template_id or template_id == "notset":
        return False
    try:
        sms_ir = SmsIr(settings.sms_api_key)
        sms_ir.send_verify_code(
            number=str(phone).strip(),
            template_id=template_id,
            parameters=[{
                "name" : "ORDERID",
                "value": str(orderid),
            }],
        )
        return True
    except Exception as e:
        print(f"Error in send_order_cancel: {e}")
        return False

def send_refill_request_sms(phone, orderid=None, code=None, **kwargs):
    final_id = orderid or code or kwargs.get('order_id') or ""
    settings = get_site_settings()
    if not settings or not settings.sms_api_key or settings.sms_api_key == "notset":
        return False
    template_id = getattr(settings, 'sms_pattern_code_refill', None)
    if not template_id or template_id == "notset":
        template_id = "602209"
    try:
        sms_ir = SmsIr(settings.sms_api_key)
        sms_ir.send_verify_code(
            number=str(phone).strip(),
            template_id=template_id,
            parameters=[{
                "name" : "ORDERID",
                "value": str(final_id),
            }],
        )
        return True
    except Exception as e:
        print(f"Error in send_refill_request_sms: {e}")
        return False

def send_refill_completed_sms(phone, orderid=None, code=None, **kwargs):
    """
    ارسال پیامک تکمیل عملیات جبران ریزش با کد پترن 229536 و متغیر ORDERID
    """
    final_id = orderid or code or kwargs.get('order_id') or ""
    settings = get_site_settings()
    if not settings or not settings.sms_api_key or settings.sms_api_key == "notset":
        return False
    template_id = getattr(settings, 'sms_pattern_code_refill_complete', None)
    if not template_id or template_id == "notset":
        template_id = "229536"
    try:
        sms_ir = SmsIr(settings.sms_api_key)
        sms_ir.send_verify_code(
            number=str(phone).strip(),
            template_id=str(template_id),
            parameters=[{
                "name" : "ORDERID",
                "value": str(final_id),
            }],
        )
        return True
    except Exception as e:
        print(f"Error in send_refill_completed_sms: {e}")
        return False

def send_wallet_charge_sms(phone, price):
    """
    ارسال پیامک شارژ موفق و افزایش موجودی کاربر با کد پترن 450882
    متغیر: price (حاوی موجودی فعلی کاربر)
    """
    settings = get_site_settings()
    if not settings or not settings.sms_api_key or settings.sms_api_key == "notset":
        return False
    template_id = getattr(settings, 'sms_pattern_code_wallet_charge', None)
    if not template_id or template_id == "notset":
        template_id = "450882"
    try:
        clean_price = str(int(round(float(price))))
    except (ValueError, TypeError):
        clean_price = str(price).split('.')[0]
    try:
        sms_ir = SmsIr(settings.sms_api_key)
        sms_ir.send_verify_code(
            number=str(phone).strip(),
            template_id=str(template_id),
            parameters=[{
                "name" : "price",
                "value": clean_price,
            }],
        )
        return True
    except Exception as e:
        print(f"Error in send_wallet_charge_sms: {e}")
        return False

def send_discount_coupon_sms(phone):
    """
    ارسال پیامک کد تخفیف برای سفارشات در انتظار پرداخت با کد پترن 430810
    پارامتر پترن: phone حاوی شماره تماس کاربر دریافت‌کننده
    """
    settings = get_site_settings()
    if not settings or not settings.sms_api_key or settings.sms_api_key == "notset":
        return False
    clean_phone = str(phone).strip()
    if not clean_phone:
        return False
    template_id = 430810
    try:
        sms_ir = SmsIr(settings.sms_api_key)
        resp = sms_ir.send_verify_code(
            number=clean_phone,
            template_id=template_id,
            parameters=[{
                "name": "phone",
                "value": clean_phone
            }]
        )
        if hasattr(resp, "status_code") and resp.status_code == 200:
            try:
                data = resp.json()
                return data.get("status") == 1
            except Exception:
                return True
        return False
    except Exception as e:
        print(f"Error in send_discount_coupon_sms: {e}")
        return False
    settings = get_site_settings()
    if not settings or not settings.panel_api_key or settings.panel_api_key == "notset":
        return None
    headers = {
        "User-Agent": "Mozilla/4.0 (compatible; MSIE 5.01; Windows NT 5.0)"
    }
    post_data["key"] = settings.panel_api_key
    try:
        response = requests.post('https://justanotherpanel.com/api/v2', data=post_data, headers=headers, timeout=10)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        print(f"Error: {e}")
        return None
        
def get_balance():
    response = connect({"action": "balance"})
    return response.json()['balance'] if response else None
    
def set_order(service, data):
    tobe_sent = {"action": "add", "service": int(service)}
    tobe_sent.update(data)
    response = connect(tobe_sent)
    return response.json() if response else None
    
def get_status(id):
    response = connect({"action": "status", "order": int(id)})
    return response.json() if response else None
    
def post_to_zibal(parameters):
    url = f"https://gateway.zibal.ir/v1/verify"
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(
        url,
        json=parameters,
        headers=headers,
        timeout=15
    )
    response.raise_for_status()
    return response.json()

# ----------------------------------------------------
# Persian/Arabic Digits Normalization
# ----------------------------------------------------
PERSIAN_ARABIC_DIGITS_TRANS = str.maketrans(
    '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
    '01234567890123456789'
)

def to_english_digits(text):
    """
    Converts any Persian or Arabic digits in `text` to English ASCII digits (0-9).
    """
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return text
    return str(text).translate(PERSIAN_ARABIC_DIGITS_TRANS)

def clean_phone_number(phone):
    """
    Normalizes a phone number to standard English digits and formats as 11-digit Iranian mobile (09XXXXXXXXX)
    or returns cleaned digits.
    """
    if not phone:
        return ""
    digits = re.sub(r'\D', '', to_english_digits(str(phone)))
    if not digits:
        return ""
    if len(digits) == 10 and digits.startswith('9'):
        return '0' + digits
    if len(digits) == 12 and digits.startswith('989'):
        return '0' + digits[2:]
    if len(digits) == 13 and digits.startswith('00989'):
        return '0' + digits[4:]
    return digits

def normalize_digits_data(data):
    """
    Recursively converts Persian/Arabic digits in strings within dicts, lists, tuples, or strings.
    """
    if isinstance(data, str):
        return data.translate(PERSIAN_ARABIC_DIGITS_TRANS)
    elif isinstance(data, dict):
        return {k: normalize_digits_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [normalize_digits_data(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(normalize_digits_data(item) for item in data)
    return data

