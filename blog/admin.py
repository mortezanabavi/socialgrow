from django.contrib import admin
from .models import BlogPost, BlogCategory, BlogTag


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title",)


@admin.register(BlogTag)
class BlogTagAdmin(admin.ModelAdmin):
    list_display = ("title",)
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title",)


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "category",
        "status",
        "views",
        "author_name",
        "published_at",
    )

    list_filter = (
        "status",
        "category",
        "is_featured",
    )

    search_fields = (
        "title",
        "short_description",
        "content",
    )

    list_editable = (
        "status",
    )

    prepopulated_fields = {
        "slug": ("title",)
    }

    raw_id_fields = ("featured_product",)
    filter_horizontal = (
        "tags",
        "related_products",
    )

    readonly_fields = (
        "views",
        "created_at",
        "updated_at",
    )

    date_hierarchy = "published_at"

    fieldsets = (

        ("اطلاعات مقاله", {
            "fields": (
                "title",
                "slug",
                "category",
                "tags",
            )
        }),

        ("محصولات و پیشنهادات مرتبط با مقاله", {
            "fields": (
                "featured_product",
                "related_products",
            ),
            "description": "می‌توانید محصول «پیشنهاد ویژه خوانندگان» (بنر جذاب بالای محتوا و دکمه چسبان) را به دلخواه انتخاب کنید. همچنین محصولات مرتبط با این مقاله را تیک بزنید / انتخاب کنید تا در انتهای پست نمایش داده شوند. در صورت خالی بودن، به صورت خودکار و هوشمند انتخاب می‌شوند."
        }),

        ("تصویر", {
            "fields": (
                "image",
            )
        }),

        ("محتوا", {
            "fields": (
                "short_description",
                "content",
            )
        }),

        ("اطلاعات انتشار", {
            "fields": (
                "author_name",
                "status",
                "is_featured",
                "reading_time",
                "published_at",
            )
        }),

        ("سئو", {
            "classes": ("collapse",),
            "fields": (
                "seo_title",
                "seo_description",
            )
        }),

        ("آمار", {
            "classes": ("collapse",),
            "fields": (
                "views",
                "created_at",
                "updated_at",
            )
        }),

    )