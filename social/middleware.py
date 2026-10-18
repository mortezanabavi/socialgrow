import json
import logging

logger = logging.getLogger(__name__)

PERSIAN_ARABIC_DIGITS_TRANS = str.maketrans(
    '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
    '01234567890123456789'
)

def to_english_digits(val):
    if val is None:
        return val
    if isinstance(val, (int, float)):
        return val
    return str(val).translate(PERSIAN_ARABIC_DIGITS_TRANS)

def normalize_digits_data(data):
    if isinstance(data, str):
        return data.translate(PERSIAN_ARABIC_DIGITS_TRANS)
    elif isinstance(data, dict):
        return {k: normalize_digits_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [normalize_digits_data(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(normalize_digits_data(item) for item in data)
    return data

class NormalizeDigitsMiddleware:
    """
    Global Django Middleware to automatically convert all Persian and Arabic
    digits in incoming HTTP requests (GET query params, POST form data, and JSON bodies)
    to standard English ASCII digits (0-9) before any view, form, serializer, or model processes them.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Normalize GET query parameters
        if request.GET:
            try:
                request.GET._mutable = True
                for key in list(request.GET.keys()):
                    values = request.GET.getlist(key)
                    normalized_values = [v.translate(PERSIAN_ARABIC_DIGITS_TRANS) if isinstance(v, str) else v for v in values]
                    request.GET.setlist(key, normalized_values)
                request.GET._mutable = False
            except Exception as e:
                logger.warning(f"Error normalizing request.GET: {e}")

        # 2. Normalize POST form parameters
        if request.POST:
            try:
                request.POST._mutable = True
                for key in list(request.POST.keys()):
                    values = request.POST.getlist(key)
                    normalized_values = [v.translate(PERSIAN_ARABIC_DIGITS_TRANS) if isinstance(v, str) else v for v in values]
                    request.POST.setlist(key, normalized_values)
                request.POST._mutable = False
            except Exception as e:
                logger.warning(f"Error normalizing request.POST: {e}")

        # 3. Normalize JSON body (for fetch / AJAX / REST API)
        content_type = request.META.get('CONTENT_TYPE', '')
        if 'application/json' in content_type:
            try:
                body_bytes = request.body
                if body_bytes:
                    data = json.loads(body_bytes.decode('utf-8'))
                    normalized_data = normalize_digits_data(data)
                    new_body_str = json.dumps(normalized_data, ensure_ascii=False)
                    request._body = new_body_str.encode('utf-8')
            except Exception as e:
                logger.warning(f"Error normalizing request.body JSON: {e}")

        response = self.get_response(request)
        return response
