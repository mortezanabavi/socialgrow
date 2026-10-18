from django.urls import path
from social import views
from .views import SubmitOrderAPIView, FindOrderByCodeAPIView
from .sitemaps import ProductSitemap
from django.contrib.sitemaps.views import sitemap

sitemaps = {
    "products": ProductSitemap(),
}

urlpatterns = [
    path('api/recent-orders/', views.recent_orders_api, name='recent_orders_api'),
    path('', views.home, name='home'),
    path('terms', views.terms, name='terms'),
    path('terms/', views.terms),
    path("sitemap-products.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap-products"),
    path('faq/', views.faqs, name='faq'),
    path('faq', views.faqs),
    path('login', views.log_in, name='login'),
    path('submit-order', SubmitOrderAPIView.as_view(), name='submit-order'),
    path('validate-coupon', views.validate_coupon, name="validate_coupon_bare"),
    path('validate-coupon/', views.validate_coupon, name="validate_coupon"),
    path('track-order', views.track_order, name='track-order'),
    path('track-order/', views.track_order),
    path('request-refill', views.request_refill, name='request-refill'),
    path('request-refill/', views.request_refill, name='request-refill-slash'),
    path('find-order', FindOrderByCodeAPIView.as_view(), name='find-order'),
    path('verify', views.verify_payment, name='verify-payment'),
    path('inquiry', views.inquiry, name='inquiry'),
    path('inquiry/', views.inquiry),
    path("trx-payment/<str:order_id>", views.trx_payment, name="trx_payment"),
    path("paid/<str:order_id>", views.paid, name="paid"),
    path('dashboard', views.dashboard, name='dashboard'),
    path('payment', views.payment, name='payment'),
    path('products/', views.show_products, name='product'),
    path('addfunds', views.addfunds, name='addfunds'),
    path('addbalance', views.increaseBalance, name='addbalance'),
    path('checkpayment', views.check_card, name='checkpayment'),
    path('tickets', views.tickets, name='tickets'),
    path('orders', views.orders, name='orders'),
    path("view-ticket/<str:tracking_code>", views.view_ticket, name="view_ticket"),
    path("view-ticket/<str:tracking_code>/reply", views.reply_ticket, name="reply"),
    path("new-order", views.new_order, name="neworder"),
    path("submit-ticket", views.submit_ticket, name="submitticket"),
    path("post-ticket", views.post_ticket, name="postticket"),
    path("userinfo", views.userinfo, name="userinfo"),
    path("changeinfo", views.changeinfo, name="changeinfo"),
    path("robots.txt", views.robots_txt, name="robotstxt"),
    path("25428846.txt", views.einamad, name="25428846"),
    path('services/<slug:slug>/', views.services, name='service_details'),
    path("notify-me", views.notify_me, name="notify_me"),
    path("api/chat/init/", views.chat_init, name="chat_init"),
    path("api/chat/send/", views.chat_send_message, name="chat_send_message"),
    path("api/chat/poll/", views.chat_poll_messages, name="chat_poll_messages"),
    path("api/chat/read/", views.chat_mark_read, name="chat_mark_read"),
    path("api/chat/telegram-webhook/", views.telegram_webhook, name="chat_telegram_webhook"),
]
