from django.db import models
from django.urls import reverse
from django_ckeditor_5.fields import CKEditor5Field
import jdatetime
from social.utils import clean_content
from django.utils import timezone

class BlogCategory(models.Model):

    title = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="نام دسته بندی"
    )

    slug = models.SlugField(
        max_length=120,
        unique=True,
        allow_unicode=True,
        verbose_name="اسلاگ"
    )

    description = models.TextField(
        blank=True,
        verbose_name="توضیحات"
    )

    image = models.ImageField(
        upload_to="blog/category/",
        blank=True,
        null=True,
        verbose_name="تصویر"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد"
    )

    class Meta:
        ordering = ["title"]
        verbose_name = "دسته بندی"
        verbose_name_plural = "دسته بندی ها"

    def __str__(self):
        return self.title


class BlogTag(models.Model):

    title = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="نام برچسب"
    )

    slug = models.SlugField(
        max_length=60,
        unique=True,
        allow_unicode=True,
        verbose_name="اسلاگ"
    )

    class Meta:
        ordering = ["title"]
        verbose_name = "برچسب"
        verbose_name_plural = "برچسب ها"

    def __str__(self):
        return self.title


class BlogPost(models.Model):

    class Status(models.IntegerChoices):

        DRAFT = 1, "پیش نویس"

        PUBLISHED = 2, "منتشر شده"


    title = models.CharField(
        max_length=250,
        verbose_name="عنوان مقاله"
    )

    slug = models.SlugField(
        max_length=260,
        unique=True,
        allow_unicode=True,
        verbose_name="اسلاگ"
    )

    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name="posts",
        verbose_name="دسته بندی"
    )

    tags = models.ManyToManyField(
        BlogTag,
        blank=True,
        related_name="posts",
        verbose_name="برچسب ها"
    )

    featured_product = models.ForeignKey(
        "social.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="featured_in_blog_posts",
        verbose_name="محصول پیشنهاد ویژه (بنر مقاله)"
    )

    related_products = models.ManyToManyField(
        "social.Product",
        blank=True,
        related_name="blog_posts",
        verbose_name="محصولات مرتبط"
    )

    author_name = models.CharField(
        max_length=100,
        default="تیم تحریریه",
        verbose_name="نام نویسنده"
    )

    image = models.ImageField(
        upload_to="blog/posts/",
        verbose_name="تصویر شاخص"
    )

    short_description = models.TextField(
        max_length=350,
        verbose_name="خلاصه مقاله"
    )

    content = models.TextField("متن مقاله")

    reading_time = models.PositiveSmallIntegerField(
        default=5,
        verbose_name="زمان مطالعه (دقیقه)"
    )

    views = models.PositiveIntegerField(
        default=0,
        verbose_name="تعداد بازدید"
    )

    is_featured = models.BooleanField(
        default=False,
        verbose_name="مطلب ویژه"
    )

    status = models.PositiveSmallIntegerField(
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="وضعیت"
    )

    seo_title = models.CharField(
        max_length=250,
        blank=True,
        verbose_name="عنوان سئو"
    )

    seo_description = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="توضیحات سئو"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخرین بروزرسانی"
    )

    published_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="تاریخ انتشار"
    )

    class Meta:
        ordering = ["-published_at"]
        verbose_name = "مقاله"
        verbose_name_plural = "مقالات"
        
    def save(self, *args, **kwargs):
        self.content = clean_content(self.content)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse(
            "article_detail",
            kwargs={
                "slug": self.slug
            }
        )

    def increase_view(self):
        self.views += 1
        self.save(update_fields=["views"])

    def get_seo_title(self):
        return self.seo_title or self.title

    def get_seo_description(self):
        return self.seo_description or self.short_description
        
    def get_date(self):
        if self.published_at:
            local_time = self._safe_localtime(self.published_at)
            j_date = jdatetime.datetime.fromgregorian(datetime=local_time)
            months = [
                "",
                "فروردین", "اردیبهشت", "خرداد",
                "تیر", "مرداد", "شهریور",
                "مهر", "آبان", "آذر",
                "دی", "بهمن", "اسفند"
            ]
            formatted_date = f"{j_date.day} {months[j_date.month]} {j_date.year}"
            return formatted_date
        return ""
    
    def published_at_iso(self):
        if self.published_at:
            return self._safe_localtime(self.published_at).isoformat(timespec='seconds')
        return ""
    
    def updated_at_iso(self):
        if self.updated_at:
            return self._safe_localtime(self.updated_at).isoformat(timespec='seconds')
        return ""
    
    @staticmethod
    def _safe_localtime(value):
        if timezone.is_naive(value):
            return value
        return timezone.localtime(value)