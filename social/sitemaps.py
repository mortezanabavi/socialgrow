from django.contrib.sitemaps import Sitemap
from .models import Product


class ProductSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Product.objects.filter(
            is_available=True
        ).order_by("id")