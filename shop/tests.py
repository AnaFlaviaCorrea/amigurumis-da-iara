from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
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


class CartViewTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Pets")
        self.product = Product.objects.create(
            category=category,
            name="Pet pronta entrega",
            short_description="Pet disponível.",
            description="Descrição do pet.",
            price=Decimal("150.00"),
            product_type=Product.ProductType.READY,
            stock=2,
            main_image=SimpleUploadedFile("pet-cart.jpg", b"imagem", content_type="image/jpeg"),
        )

    def test_add_product_to_cart(self):
        response = self.client.post(
            reverse("shop:cart_add", args=[self.product.id]),
            {"quantity": 1},
            follow=True,
        )

        self.assertRedirects(response, reverse("shop:cart_detail"))
        self.assertEqual(self.client.session["cart"][str(self.product.id)]["quantity"], 1)
        self.assertContains(response, "R$ 150,00")

    def test_update_cart_quantity(self):
        self.client.post(
            reverse("shop:cart_add", args=[self.product.id]),
            {"quantity": 1},
        )
        self.client.post(
            reverse("shop:cart_update", args=[self.product.id]),
            {"quantity": 2, "replace": "on"},
        )

        self.assertEqual(self.client.session["cart"][str(self.product.id)]["quantity"], 2)

    def test_cart_does_not_exceed_ready_stock(self):
        response = self.client.post(
            reverse("shop:cart_add", args=[self.product.id]),
            {"quantity": 3},
            follow=True,
        )

        self.assertNotIn(str(self.product.id), self.client.session.get("cart", {}))
        self.assertContains(response, "Temos apenas 2 unidade(s) disponível(is).")

    def test_repeated_add_does_not_exceed_ready_stock(self):
        add_url = reverse("shop:cart_add", args=[self.product.id])
        self.client.post(add_url, {"quantity": 2})
        response = self.client.post(add_url, {"quantity": 1}, follow=True)

        self.assertEqual(self.client.session["cart"][str(self.product.id)]["quantity"], 2)
        self.assertContains(response, "Temos apenas 2 unidade(s) disponível(is).")

    def test_remove_product_from_cart(self):
        self.client.post(
            reverse("shop:cart_add", args=[self.product.id]),
            {"quantity": 1},
        )
        response = self.client.post(
            reverse("shop:cart_remove", args=[self.product.id]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(str(self.product.id), self.client.session.get("cart", {}))
        self.assertContains(response, "Seu carrinho está vazio")

    def test_cart_mutations_only_accept_post(self):
        response = self.client.get(reverse("shop:cart_add", args=[self.product.id]))

        self.assertEqual(response.status_code, 405)


class PortfolioImportCommandTests(TestCase):
    def test_import_is_incremental_and_recognizes_renamed_images(self):
        with TemporaryDirectory() as source_directory, TemporaryDirectory() as media_directory:
            source = Path(source_directory)
            pets = source / "pets"
            dolls = source / "bonecas"
            pets.mkdir()
            dolls.mkdir()
            pet_image = pets / "pet01.png"
            doll_image = dolls / "boneca01.jpg"
            pet_image.write_bytes(b"imagem-pet-v1")
            doll_image.write_bytes(b"imagem-boneca")

            with override_settings(MEDIA_ROOT=media_directory):
                call_command("import_portfolio_products", source=source)

                self.assertEqual(Product.objects.count(), 2)
                pet_product = Product.objects.get(portfolio_source="pets/pet01.png")
                original_hash = pet_product.portfolio_hash
                self.assertFalse(pet_product.active)
                self.assertIsNone(pet_product.price)
                self.assertEqual(pet_product.category.name, "Pets realistas")

                call_command("import_portfolio_products", source=source)
                self.assertEqual(Product.objects.count(), 2)

                (pets / "pet02.png").write_bytes(b"imagem-pet-nova")
                call_command("import_portfolio_products", source=source)
                self.assertEqual(Product.objects.count(), 3)

                pet_image.write_bytes(b"imagem-pet-v2")
                call_command("import_portfolio_products", source=source)
                pet_product.refresh_from_db()
                self.assertNotEqual(pet_product.portfolio_hash, original_hash)

                renamed = pets / "pet-renomeado.png"
                pet_image.rename(renamed)
                call_command("import_portfolio_products", source=source)
                pet_product.refresh_from_db()
                self.assertEqual(Product.objects.count(), 3)
                self.assertEqual(pet_product.portfolio_source, "pets/pet-renomeado.png")

    def test_dry_run_does_not_create_products(self):
        with TemporaryDirectory() as source_directory:
            source = Path(source_directory)
            (source / "santinhas").mkdir()
            (source / "santinhas" / "santinha01.png").write_bytes(b"imagem")

            call_command("import_portfolio_products", source=source, dry_run=True)

            self.assertEqual(Product.objects.count(), 0)
