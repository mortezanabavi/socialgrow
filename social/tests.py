from django.test import TestCase, Client
from django.urls import reverse
from .models import Product, SiteSettings
from accounts.models import CustomUser


class SocialViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.settings = SiteSettings.objects.create(
            name="سوشال گرو",
            domain="localhost:8000"
        )
        self.product = Product.objects.create(
            uni_code=1001,
            name="تست فالوور",
            slug="test-follower",
            service_id=1,
            en="instagram",
            app="2",
            price=1.5,
            min_order=100,
            max_order=10000,
            is_available=True
        )

    def test_home_page(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "سوشال گرو")

    def test_products_page(self):
        response = self.client.get(reverse('product'))
        self.assertEqual(response.status_code, 200)

    def test_service_detail_page(self):
        response = self.client.get(reverse('service_details', kwargs={'slug': self.product.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)

    def test_terms_page(self):
        response = self.client.get(reverse('terms'))
        self.assertEqual(response.status_code, 200)

    def test_faq_page(self):
        response = self.client.get(reverse('faq'))
        self.assertEqual(response.status_code, 200)
