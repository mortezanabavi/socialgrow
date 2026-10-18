import re
from social.utils import to_english_digits

def validate_iran_phone(phone):
    if not phone:
        return False
    phone = to_english_digits(str(phone)).strip()
    pattern = r'^(\+98|0)?9\d{9}$'
    return bool(re.match(pattern, phone))