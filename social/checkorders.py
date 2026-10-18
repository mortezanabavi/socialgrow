import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "socialgrow.settings"
)

django.setup()

from social.models import Order
from social.utils import get_status, send_order_complete
import time

# Filter only active/in-progress orders instead of the entire database
orders = Order.objects.filter(status__in=["2", "3", 2, 3])
for order in orders:
    if str(order.orderid).isnumeric():
        try:
            result = get_status(order.orderid)
            if not result or not isinstance(result, dict):
                continue

            api_status = result.get("status")

            if api_status == "Completed" and str(order.status) != "4":
                try:
                    send_order_complete(order.receiver_phone, order.code)
                except Exception as ex:
                    print(f"SMS complete error: {ex}")
                order.status = 4
                order.save(update_fields=["status"])

            elif api_status in ("Cancelled", "Partial") and str(order.status) != "5":
                order.status = 5
                order.save(update_fields=["status"])

            elif api_status == "Processing" and str(order.status) != "3":
                order.status = 3
                order.save(update_fields=["status"])
        except Exception as e:
            print(f"Error checking order {order.id}: {e}")
