from rest_framework import serializers
from .models import Order

class OrderSerializer(serializers.ModelSerializer):
    coupon_code = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Order
        fields = ['product', 'page_address', 'count_order', 'status', 'payment_method', 'receiver_phone', 'coupon_code', 'has_bump', 'bump_posts_count', 'bump_likes_each', 'bump_views_each', 'bump_price', 'bump_details']

    def create(self, validated_data):
        validated_data.pop('coupon_code', None)
        return super().create(validated_data)