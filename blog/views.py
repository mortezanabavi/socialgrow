import random
from django.shortcuts import render, get_object_or_404
from .models import BlogPost, BlogCategory
from html import unescape
from social.models import SiteSettings, Product
from django.db.models import F, Q
from social.utils import clean_content
import time

def blog_index(request):
    return render(request, "post.html")

def blog_view(request):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()

    # Published posts (Status.PUBLISHED = 2)
    base_qs = BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED)
    if not base_qs.exists():
        base_qs = BlogPost.objects.all()

    posts_qs = base_qs
    if query:
        posts_qs = posts_qs.filter(
            Q(title__icontains=query) |
            Q(short_description__icontains=query) |
            Q(slug__icontains=query)
        )

    if category_slug:
        posts_qs = posts_qs.filter(category__slug=category_slug)

    all_posts = list(posts_qs.order_by('-published_at', '-id'))

    top_posts = list(base_qs.order_by('-views', '-id')[:6])
    recent_posts = list(base_qs.order_by('-published_at', '-id')[:6])
    offer_posts = list(base_qs.filter(is_featured=True).order_by('-published_at', '-id')[:6])
    if not offer_posts:
        offer_posts = recent_posts[:4]

    categories = list(BlogCategory.objects.all())
    featured_post = base_qs.filter(is_featured=True).order_by('-published_at').first()
    if not featured_post and all_posts:
        featured_post = all_posts[0]

    return render(request, "blog.html", {
        "current_time": int(time.time()),
        "settings": SiteSettings.objects.first(),
        "posts": all_posts,
        "all_posts": all_posts,
        "top": top_posts,
        "recent": recent_posts,
        "offer": offer_posts,
        "categories": categories,
        "featured_post": featured_post,
        "search_query": query,
        "selected_category": category_slug,
        "total_posts_count": base_qs.count()
    })

def article_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug)
    post.content = unescape(post.content)

    # 1. Increment views with session throttle
    session_key = f'viewed_post_{post.id}'
    if not request.session.get(session_key, False):
        BlogPost.objects.filter(id=post.id).update(views=F('views') + 1)
        request.session[session_key] = True
        post.refresh_from_db()

    # 2. Related Blog Posts
    if post.category:
        related_posts = BlogPost.objects.filter(
            category=post.category
        ).exclude(id=post.id).order_by('-published_at')[:4]
    else:
        related_posts = BlogPost.objects.exclude(id=post.id).order_by('-published_at')[:4]

    recent_posts = BlogPost.objects.order_by('-published_at')[:5]

    # 3. Product Matching
    related_products = []
    try:
        # Check if admin manually selected related products in Django admin
        manual_products = list(post.related_products.filter(is_available=True))
        if manual_products:
            related_products = manual_products
        else:
            # Fall back to intelligent keyword/category matching for SEO & High Conversion from Google
            cat_title = post.category.title if post.category else ''
            cat_slug = post.category.slug if post.category else ''
            short_desc = post.short_description or ''
            search_text = f"{post.title} {post.slug} {short_desc} {cat_title} {cat_slug}".lower()

            is_premium_post = any(k in search_text for k in ['پرمیوم', 'پریمیوم', 'premium'])
            is_stars_post = any(k in search_text for k in ['استارز', 'ستاره های تلگرام', 'ستاره تلگرام', 'stars'])

            if is_stars_post and not is_premium_post:
                # Telegram Stars post: prioritize stars product, then premium
                stars_prods = list(Product.objects.filter(is_available=True).filter(
                    Q(slug__icontains='stars') | Q(name__contains='استارز')
                ).order_by('id'))
                related_products.extend(stars_prods)

                exclude_ids = [p.id for p in related_products]
                prem_prods = list(Product.objects.filter(is_available=True).filter(
                    Q(slug__icontains='premium') | Q(name__contains='پرمیوم') | Q(name__contains='پریمیوم')
                ).exclude(id__in=exclude_ids).order_by('id')[:4 - len(related_products)])
                related_products.extend(prem_prods)

            elif is_premium_post and not is_stars_post:
                # Telegram Premium post: prioritize premium products (3m, 6m, 12m), then stars
                prem_prods = list(Product.objects.filter(is_available=True).filter(
                    Q(slug__icontains='premium') | Q(name__contains='پرمیوم') | Q(name__contains='پریمیوم')
                ).order_by('id')[:3])
                related_products.extend(prem_prods)

                exclude_ids = [p.id for p in related_products]
                stars_prods = list(Product.objects.filter(is_available=True).filter(
                    Q(slug__icontains='stars') | Q(name__contains='استارز')
                ).exclude(id__in=exclude_ids).order_by('id')[:4 - len(related_products)])
                related_products.extend(stars_prods)

            elif is_stars_post and is_premium_post:
                # Post mentions both: check which is the primary subject in slug or title
                if any(k in f"{post.slug} {post.title}".lower() for k in ['stars', 'استارز', 'ستاره']):
                    stars_prods = list(Product.objects.filter(is_available=True).filter(
                        Q(slug__icontains='stars') | Q(name__contains='استارز')
                    ).order_by('id'))
                    related_products.extend(stars_prods)
                    exclude_ids = [p.id for p in related_products]
                    prem_prods = list(Product.objects.filter(is_available=True).filter(
                        Q(slug__icontains='premium') | Q(name__contains='پرمیوم') | Q(name__contains='پریمیوم')
                    ).exclude(id__in=exclude_ids).order_by('id')[:4 - len(related_products)])
                    related_products.extend(prem_prods)
                else:
                    prem_prods = list(Product.objects.filter(is_available=True).filter(
                        Q(slug__icontains='premium') | Q(name__contains='پرمیوم') | Q(name__contains='پریمیوم')
                    ).order_by('id')[:3])
                    related_products.extend(prem_prods)
                    exclude_ids = [p.id for p in related_products]
                    stars_prods = list(Product.objects.filter(is_available=True).filter(
                        Q(slug__icontains='stars') | Q(name__contains='استارز')
                    ).exclude(id__in=exclude_ids).order_by('id')[:4 - len(related_products)])
                    related_products.extend(stars_prods)

            if not related_products:
                app_target = None
                if any(k in search_text for k in ['telegram', 'تلگرام', 'ممبر', 'تبچی', 'ری‌اکشن', 'پروکسی']):
                    app_target = "1" # Telegram
                elif any(k in search_text for k in ['instagram', 'اینستاگرام', 'اینستا', 'فالوور', 'فالور', 'استوری', 'ریلز', 'اکسپلور']):
                    app_target = "2" # Instagram
                elif any(k in search_text for k in ['youtube', 'یوتیوب', 'سابسکرایب']):
                    app_target = "3" # YouTube
                elif any(k in search_text for k in ['twitter', 'توییتر', 'توییت', 'x.com']):
                    app_target = "4" # Twitter / X
                elif any(k in search_text for k in ['tiktok', 'تیک‌تاک', 'تیک تاک']):
                    app_target = "5" # TikTok

                if app_target:
                    related_products = list(Product.objects.filter(app=app_target, is_available=True).order_by('-selled_count', 'id')[:4])

            if len(related_products) < 4:
                exclude_ids = [p.id for p in related_products]
                if post.category and post.category.slug:
                    cat_products = Product.objects.filter(en=post.category.slug, is_available=True).exclude(id__in=exclude_ids)[:4 - len(related_products)]
                    related_products.extend(list(cat_products))
                    exclude_ids = [p.id for p in related_products]

                if len(related_products) < 4:
                    top_products = Product.objects.filter(is_available=True).exclude(id__in=exclude_ids).order_by('-selled_count', 'id')[:4 - len(related_products)]
                    related_products.extend(list(top_products))

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error matching related products for post {post.id}: {e}")
        try:
            related_products = list(Product.objects.filter(is_available=True)[:4])
        except Exception:
            related_products = []

    # Set featured product: manual admin selection takes precedence
    if post.featured_product and post.featured_product.is_available:
        featured_product = post.featured_product
    else:
        featured_product = related_products[0] if related_products else None

    context = {
        "current_time": int(time.time()),
        "settings": SiteSettings.objects.first(),
        "post": post,
        "related_product": related_products,
        "related_products": related_products,
        "featured_product": featured_product,
        "related_posts": related_posts,
        "recent": recent_posts
    }
    return render(request, "post.html", context)
