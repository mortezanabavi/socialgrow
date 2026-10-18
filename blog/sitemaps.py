from django.contrib.sitemaps import Sitemap
from .models import BlogPost


class BlogSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return (
            BlogPost.objects.filter(
                status=BlogPost.Status.PUBLISHED
            )
            .exclude(published_at__isnull=True)
            .select_related("category")
            .prefetch_related("tags")
            .order_by("-published_at")
        )

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()