from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product


class ProductModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Pets")

    def make_product(self, **overrides):
        data = {
            "category": self.category,
            "name": "Cachorrinho realista",
            "short_description": "Uma lembrança criada à mão.",
            "description": "Peça artesanal feita com cuidado.",
            "price": Decimal("350.00"),
            "product_type": Product.ProductType.READY,
            "stock": 1,
            "main_image": SimpleUploadedFile("pet.jpg", b"imagem", content_type="image/jpeg"),
        }
        data.update(overrides)
        return Product(**data)

    def test_ready_product_with_stock_is_available(self):
        product = self.make_product()
        product.full_clean(exclude=("main_image",))
        self.assertTrue(product.available)

    def test_made_to_order_requires_production_days(self):
        product = self.make_product(
            product_type=Product.ProductType.MADE_TO_ORDER,
            stock=0,
            production_days=None,
        )

        with self.assertRaises(ValidationError) as error:
            product.full_clean(exclude=("main_image",))

        self.assertIn("production_days", error.exception.message_dict)

    def test_slug_is_generated_and_unique(self):
        first = self.make_product()
        first.save()
        second = self.make_product()
        second.save()

        self.assertEqual(first.slug, "cachorrinho-realista")
        self.assertEqual(second.slug, "cachorrinho-realista-2")


class ShopViewTests(TestCase):
    def setUp(self):
        pets = Category.objects.create(name="Pets")
        dolls = Category.objects.create(name="Bonecas")
        self.ready = Product.objects.create(
            category=pets,
            name="Pet pronta entrega",
            short_description="Pet disponível.",
            description="Descrição do pet.",
            price=Decimal("320.00"),
            product_type=Product.ProductType.READY,
            stock=1,
            main_image=SimpleUploadedFile("pet.jpg", b"imagem", content_type="image/jpeg"),
        )
        self.order = Product.objects.create(
            category=dolls,
            name="Boneca sob encomenda",
            short_description="Boneca personalizada.",
            description="Descrição da boneca.",
            price=Decimal("280.00"),
            product_type=Product.ProductType.MADE_TO_ORDER,
            production_days=20,
            customizable=True,
            main_image=SimpleUploadedFile("boneca.jpg", b"imagem", content_type="image/jpeg"),
        )

    def test_catalog_displays_active_products(self):
        response = self.client.get(reverse("shop:product_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ready.name)
        self.assertContains(response, self.order.name)

    def test_catalog_filters_product_type(self):
        response = self.client.get(
            reverse("shop:product_list"),
            {"modalidade": Product.ProductType.MADE_TO_ORDER},
        )

        self.assertNotContains(response, self.ready.name)
        self.assertContains(response, self.order.name)

    def test_product_detail_displays_production_time(self):
        response = self.client.get(self.order.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Produção em até 20 dias")
