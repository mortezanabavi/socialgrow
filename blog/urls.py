from django.urls import path
from . import views

urlpatterns = [
    path('blog/', views.blog_view, name='blog_view'),
    path('blog', views.blog_view),
    path('<slug:slug>/', views.article_detail, name='article_detail'),
]
