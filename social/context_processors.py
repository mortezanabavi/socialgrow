import time
from .utils import get_site_settings

def site_settings(request):
    """
    Global context processor providing site settings, reCAPTCHA status, and timestamp.
    Guarantees templates have safe fallbacks and never break on fresh installations.
    """
    st = get_site_settings()
    site_key = getattr(st, 'recaptcha_site_key', None) if st else None
    has_recaptcha = bool(
        site_key and str(site_key).strip().lower() not in ["notset", "", "none"]
    )
    try:
        from .models import Product
        popular_products = list(Product.objects.filter(is_available=True)[:5])
    except Exception:
        popular_products = []

    return {
        "settings": st,
        "site_settings": st,
        "recaptcha_enabled": has_recaptcha,
        "current_time": int(time.time()),
        "popular_products": popular_products,
    }

