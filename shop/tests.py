import json
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Category, Order, OrderItem, PaymentAttempt, Product


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
            "main_image": SimpleUploadedFile(
                "pet.jpg", b"imagem", content_type="image/jpeg"
            ),
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
            main_image=SimpleUploadedFile(
                "pet.jpg", b"imagem", content_type="image/jpeg"
            ),
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
            main_image=SimpleUploadedFile(
                "boneca.jpg", b"imagem", content_type="image/jpeg"
            ),
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
            main_image=SimpleUploadedFile(
                "pet-cart.jpg", b"imagem", content_type="image/jpeg"
            ),
        )

    def test_add_product_to_cart(self):
        response = self.client.post(
            reverse("shop:cart_add", args=[self.product.id]),
            {"quantity": 1},
            follow=True,
        )

        self.assertRedirects(response, reverse("shop:cart_detail"))
        self.assertEqual(
            self.client.session["cart"][str(self.product.id)]["quantity"], 1
        )
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

        self.assertEqual(
            self.client.session["cart"][str(self.product.id)]["quantity"], 2
        )

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

        self.assertEqual(
            self.client.session["cart"][str(self.product.id)]["quantity"], 2
        )
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


class CheckoutTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Bonecas")
        self.product = Product.objects.create(
            category=category,
            name="Boneca personalizada",
            short_description="Boneca produzida sob encomenda.",
            description="Boneca artesanal.",
            price=Decimal("275.00"),
            product_type=Product.ProductType.MADE_TO_ORDER,
            production_days=20,
            customizable=True,
            main_image=SimpleUploadedFile(
                "boneca-checkout.jpg", b"imagem", content_type="image/jpeg"
            ),
        )

    def add_product(self, quantity=1):
        self.client.post(
            reverse("shop:cart_add", args=[self.product.id]),
            {"quantity": quantity},
        )

    def test_empty_cart_cannot_open_checkout(self):
        response = self.client.get(reverse("shop:checkout"))

        self.assertRedirects(response, reverse("shop:product_list"))

    def test_pickup_checkout_creates_order_and_clears_cart(self):
        self.add_product(quantity=2)
        response = self.client.post(
            reverse("shop:checkout"),
            {
                "full_name": "Ana Cliente",
                "email": "ana@example.com",
                "phone": "(48) 99999-9999",
                "delivery_method": Order.DeliveryMethod.PICKUP,
                "customer_notes": "Entrar em contato pelo WhatsApp.",
            },
        )

        order = Order.objects.get()
        self.assertRedirects(
            response, reverse("shop:order_payment", args=[order.public_id])
        )
        self.assertEqual(order.subtotal, Decimal("550.00"))
        self.assertEqual(order.total, Decimal("550.00"))
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertTrue(order.shipping_calculated)
        self.assertEqual(OrderItem.objects.get().quantity, 2)
        self.assertEqual(self.client.session.get("cart"), None)

    def test_shipping_requires_address(self):
        self.add_product()
        response = self.client.post(
            reverse("shop:checkout"),
            {
                "full_name": "Ana Cliente",
                "email": "ana@example.com",
                "phone": "(48) 99999-9999",
                "delivery_method": Order.DeliveryMethod.SHIPPING,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe cep para receber o pedido")
        self.assertEqual(Order.objects.count(), 0)

    def test_shipping_checkout_saves_address(self):
        self.add_product()
        response = self.client.post(
            reverse("shop:checkout"),
            {
                "full_name": "Ana Cliente",
                "email": "ana@example.com",
                "phone": "(48) 99999-9999",
                "delivery_method": Order.DeliveryMethod.SHIPPING,
                "postal_code": "88101-000",
                "street": "Rua das Flores",
                "number": "100",
                "neighborhood": "Campinas",
                "city": "São José",
                "state": "sc",
            },
        )

        self.assertEqual(response.status_code, 302)
        order = Order.objects.get()
        self.assertEqual(order.state, "SC")
        self.assertEqual(order.city, "São José")
        self.assertFalse(order.shipping_calculated)

    def test_success_page_is_limited_to_last_session_order(self):
        other_order = Order.objects.create(
            full_name="Outra pessoa",
            email="outra@example.com",
            phone="48999999999",
            delivery_method=Order.DeliveryMethod.PICKUP,
            subtotal=Decimal("10.00"),
            total=Decimal("10.00"),
        )

        response = self.client.get(
            reverse("shop:order_success", args=[other_order.public_id])
        )

        self.assertRedirects(response, reverse("shop:product_list"))


@override_settings(
    MERCADO_PAGO_PUBLIC_KEY="TEST-public-key",
    MERCADO_PAGO_ACCESS_TOKEN="TEST-access-token",
)
class PaymentTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            full_name="Ana Cliente",
            email="ana@example.com",
            phone="48999999999",
            delivery_method=Order.DeliveryMethod.PICKUP,
            subtotal=Decimal("150.00"),
            shipping_calculated=True,
            total=Decimal("150.00"),
        )
        session = self.client.session
        session["last_order_id"] = str(self.order.public_id)
        session.save()

    def test_payment_page_creates_attempt(self):
        response = self.client.get(
            reverse("shop:order_payment", args=[self.order.public_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cardPaymentBrick_container")
        attempt = PaymentAttempt.objects.get()
        self.assertEqual(attempt.amount, Decimal("150.00"))

    @patch("shop.views.create_mercado_pago_order")
    def test_processed_order_updates_local_order(
        self,
        create_order,
    ):
        attempt = PaymentAttempt.objects.create(
            order=self.order,
            amount=self.order.total,
        )

        create_order.return_value = (
            201,
            {
                "id": "ORD123456",
                "status": "processed",
                "status_detail": "accredited",
                "transactions": {
                    "payments": [
                        {
                            "id": "PAY123456",
                            "status": "processed",
                            "status_detail": "accredited",
                            "payment_method": {
                                "id": "visa",
                                "type": "credit_card",
                            },
                        }
                    ]
                },
            },
        )

        response = self.client.post(
            reverse(
                "shop:process_payment",
                args=[self.order.public_id],
            ),
            data=json.dumps(
                {
                    "attempt_id": str(attempt.public_id),
                    # Este valor falso comprova que o servidor
                    # utiliza o total salvo no pedido.
                    "transaction_amount": 1,
                    "payment_method_id": "visa",
                    "payment_type_id": "credit_card",
                    "token": "test-token",
                    "installments": 1,
                    "payer": {
                        "email": "alterado@example.com",
                    },
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        attempt.refresh_from_db()

        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(attempt.provider_order_id, "ORD123456")
        self.assertEqual(attempt.provider_payment_id, "PAY123456")
        self.assertEqual(attempt.transaction_status, "processed")

        passed_order = create_order.call_args.args[0]
        self.assertEqual(passed_order.total, Decimal("150.00"))

    @patch("shop.views.create_mercado_pago_order")
    def test_failed_order_is_saved_without_marking_order_as_paid(
        self,
        create_order,
    ):
        attempt = PaymentAttempt.objects.create(
            order=self.order,
            amount=self.order.total,
        )

        create_order.return_value = (
            402,
            {
                "errors": [
                    {
                        "code": "failed",
                        "message": "The following transactions failed",
                    }
                ],
                "data": {
                    "id": "ORD-FAILED-123",
                    "status": "failed",
                    "status_detail": "failed",
                    "transactions": {
                        "payments": [
                            {
                                "id": "PAY-FAILED-123",
                                "status": "failed",
                                "status_detail": "rejected_by_issuer",
                                "payment_method": {
                                    "id": "master",
                                    "type": "credit_card",
                                },
                            }
                        ]
                    },
                },
            },
        )

        response = self.client.post(
            reverse(
                "shop:process_payment",
                args=[self.order.public_id],
            ),
            data=json.dumps(
                {
                    "attempt_id": str(attempt.public_id),
                    "payment_method_id": "master",
                    "payment_type_id": "credit_card",
                    "token": "test-token",
                    "installments": 1,
                    "payer": {
                        "identification": {
                            "type": "CPF",
                            "number": "12345678909",
                        }
                    },
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        attempt.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.PENDING,
        )
        self.assertEqual(attempt.status, "failed")
        self.assertEqual(
            attempt.transaction_status,
            "failed",
        )
        self.assertEqual(
            attempt.transaction_status_detail,
            "rejected_by_issuer",
        )
        self.assertEqual(
            attempt.provider_order_id,
            "ORD-FAILED-123",
        )

    @patch("shop.views.create_mercado_pago_order")
    def test_processing_order_does_not_mark_order_as_paid(
        self,
        create_order,
    ):
        attempt = PaymentAttempt.objects.create(
            order=self.order,
            amount=self.order.total,
        )

        create_order.return_value = (
            201,
            {
                "id": "ORD-PROCESSING-123",
                "status": "processing",
                "status_detail": "in_process",
                "transactions": {
                    "payments": [
                        {
                            "id": "PAY-PROCESSING-123",
                            "status": "processing",
                            "status_detail": "in_process",
                            "payment_method": {
                                "id": "master",
                                "type": "credit_card",
                            },
                        }
                    ]
                },
            },
        )

        response = self.client.post(
            reverse(
                "shop:process_payment",
                args=[self.order.public_id],
            ),
            data=json.dumps(
                {
                    "attempt_id": str(attempt.public_id),
                    "payment_method_id": "master",
                    "payment_type_id": "credit_card",
                    "token": "test-token",
                    "installments": 1,
                    "payer": {
                        "identification": {
                            "type": "CPF",
                            "number": "12345678909",
                        }
                    },
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        attempt.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.PENDING,
        )
        self.assertEqual(attempt.status, "processing")
        self.assertEqual(
            attempt.transaction_status,
            "processing",
        )
        self.assertEqual(
            attempt.provider_order_id,
            "ORD-PROCESSING-123",
        )

    @patch(
        "shop.views.validate_mercado_pago_webhook",
        return_value=False,
    )
    def test_webhook_rejects_invalid_signature(
        self,
        validate_webhook,
    ):
        url = reverse("shop:mercado_pago_webhook")
        url += "?data.id=ORD-WEBHOOK-INVALID"

        response = self.client.post(
            url,
            data=json.dumps(
                {
                    "type": "order",
                    "data": {
                        "id": "ORD-WEBHOOK-INVALID",
                    },
                }
            ),
            content_type="application/json",
            HTTP_X_SIGNATURE="invalid-signature",
            HTTP_X_REQUEST_ID="request-123",
        )

        self.assertEqual(response.status_code, 401)
        validate_webhook.assert_called_once()

    @patch("shop.views.get_mercado_pago_order")
    @patch(
        "shop.views.validate_mercado_pago_webhook",
        return_value=True,
    )
    def test_webhook_ignores_unknown_order(
        self,
        validate_webhook,
        get_order,
    ):
        url = reverse("shop:mercado_pago_webhook")
        url += "?data.id=ORD-UNKNOWN"

        response = self.client.post(
            url,
            data=json.dumps(
                {
                    "type": "order",
                    "data": {
                        "id": "ORD-UNKNOWN",
                    },
                }
            ),
            content_type="application/json",
            HTTP_X_SIGNATURE="valid-signature",
            HTTP_X_REQUEST_ID="request-456",
        )

        self.assertEqual(response.status_code, 200)
        validate_webhook.assert_called_once()
        get_order.assert_not_called()

    @patch("shop.views.get_mercado_pago_order")
    @patch(
        "shop.views.validate_mercado_pago_webhook",
        return_value=True,
    )
    def test_webhook_updates_processing_order_to_paid(
        self,
        validate_webhook,
        get_order,
    ):
        attempt = PaymentAttempt.objects.create(
            order=self.order,
            amount=self.order.total,
            provider_order_id="ORD-WEBHOOK-123",
            provider_payment_id="PAY-WEBHOOK-123",
            status="processing",
            transaction_status="processing",
            transaction_status_detail="in_process",
        )

        get_order.return_value = (
            200,
            {
                "id": "ORD-WEBHOOK-123",
                "status": "processed",
                "status_detail": "accredited",
                "transactions": {
                    "payments": [
                        {
                            "id": "PAY-WEBHOOK-123",
                            "status": "processed",
                            "status_detail": "accredited",
                            "payment_method": {
                                "id": "master",
                                "type": "credit_card",
                            },
                        }
                    ]
                },
            },
        )

        url = reverse("shop:mercado_pago_webhook")
        url += "?data.id=ORD-WEBHOOK-123&type=order"

        response = self.client.post(
            url,
            data=json.dumps(
                {
                    "action": "order.processed",
                    "type": "order",
                    "data": {
                        "id": "ORD-WEBHOOK-123",
                    },
                }
            ),
            content_type="application/json",
            HTTP_X_SIGNATURE="valid-signature",
            HTTP_X_REQUEST_ID="request-789",
        )

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        attempt.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.PAID,
        )
        self.assertEqual(attempt.status, "processed")
        self.assertEqual(
            attempt.transaction_status,
            "processed",
        )
        self.assertEqual(
            attempt.status_detail,
            "accredited",
        )

        validate_webhook.assert_called_once()
        get_order.assert_called_once_with("ORD-WEBHOOK-123")

    @patch("shop.views.create_mercado_pago_order")
    def test_pix_order_saves_qr_code_and_keeps_order_pending(
        self,
        create_order,
    ):
        attempt = PaymentAttempt.objects.create(
            order=self.order,
            amount=self.order.total,
        )

        create_order.return_value = (
            201,
            {
                "id": "ORD-PIX-123",
                "status": "action_required",
                "status_detail": "waiting_transfer",
                "transactions": {
                    "payments": [
                        {
                            "id": "PAY-PIX-123",
                            "status": "action_required",
                            "status_detail": "waiting_transfer",
                            "payment_method": {
                                "id": "pix",
                                "type": "bank_transfer",
                                "qr_code": "codigo-pix-copia-e-cola",
                                "qr_code_base64": "imagem-pix-base64",
                                "ticket_url": (
                                    "https://www.mercadopago.com.br/" "sandbox/pix"
                                ),
                            },
                        }
                    ]
                },
            },
        )

        response = self.client.post(
            reverse(
                "shop:process_payment",
                args=[self.order.public_id],
            ),
            data=json.dumps(
                {
                    "attempt_id": str(attempt.public_id),
                    "payment_method_id": "pix",
                    "payment_type_id": "bank_transfer",
                    "payer": {
                        "email": self.order.email,
                    },
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("redirect_url", response.json())

        self.order.refresh_from_db()
        attempt.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.PENDING,
        )
        self.assertEqual(attempt.status, "action_required")
        self.assertEqual(
            attempt.transaction_status,
            "action_required",
        )
        self.assertEqual(attempt.payment_method_id, "pix")
        self.assertEqual(
            attempt.payment_type_id,
            "bank_transfer",
        )
        self.assertEqual(
            attempt.qr_code,
            "codigo-pix-copia-e-cola",
        )
        self.assertEqual(
            attempt.qr_code_base64,
            "imagem-pix-base64",
        )
        self.assertTrue(attempt.ticket_url)

        payment_data = create_order.call_args.args[2]

        self.assertEqual(
            payment_data["payment_method_id"],
            "pix",
        )
        self.assertEqual(
            payment_data["payment_type_id"],
            "bank_transfer",
        )
        result_response = self.client.get(response.json()["redirect_url"])

        self.assertEqual(result_response.status_code, 200)
        self.assertContains(
            result_response,
            "Copiar código Pix",
        )
        self.assertContains(
            result_response,
            "Abrir instruções do Pix",
        )
        self.assertContains(
            result_response,
            'id="pix-code"',
        )

    @patch("shop.views.create_mercado_pago_order")
    def test_boleto_saves_ticket_without_marking_order_as_paid(
        self,
        create_order,
    ):
        attempt = PaymentAttempt.objects.create(
            order=self.order,
            amount=self.order.total,
        )

        ticket_url = "https://www.mercadopago.com.br/" "staging/payments/test/ticket"

        create_order.return_value = (
            201,
            {
                "id": "ORD-BOLETO-123",
                "status": "action_required",
                "status_detail": "waiting_payment",
                "transactions": {
                    "payments": [
                        {
                            "id": "PAY-BOLETO-123",
                            "status": "action_required",
                            "status_detail": "waiting_payment",
                            "payment_method": {
                                "id": "boleto",
                                "type": "ticket",
                                "ticket_url": ticket_url,
                            },
                        }
                    ]
                },
            },
        )

        response = self.client.post(
            reverse(
                "shop:process_payment",
                args=[self.order.public_id],
            ),
            data=json.dumps(
                {
                    "attempt_id": str(attempt.public_id),
                    "payment_method_id": "boleto",
                    "payment_type_id": "ticket",
                    "payer": {
                        "identification": {
                            "type": "CPF",
                            "number": "99999999999",
                        },
                        "address": {
                            "zip_code": "06233903",
                            "street_name": "Av. das Nações Unidas",
                            "street_number": "3003",
                            "neighborhood": "Bonfim",
                            "city": "Osasco",
                            "state": "SP",
                        },
                    },
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        attempt.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.Status.PENDING,
        )
        self.assertEqual(
            attempt.status,
            PaymentAttempt.Status.ACTION_REQUIRED,
        )
        self.assertEqual(
            attempt.transaction_status,
            "action_required",
        )
        self.assertEqual(
            attempt.payment_method_id,
            "boleto",
        )
        self.assertEqual(
            attempt.payment_type_id,
            "ticket",
        )
        self.assertEqual(
            attempt.ticket_url,
            ticket_url,
        )
        self.assertEqual(
            attempt.provider_order_id,
            "ORD-BOLETO-123",
        )

        sent_payload = create_order.call_args.args[2]

        self.assertEqual(
            sent_payload["payment_type_id"],
            "ticket",
        )

    def test_shipping_order_is_not_charged_before_freight(self):
        self.order.delivery_method = Order.DeliveryMethod.SHIPPING
        self.order.shipping_calculated = False
        self.order.save()

        response = self.client.get(
            reverse("shop:order_payment", args=[self.order.public_id])
        )

        self.assertContains(response, "Estamos calculando o frete")
        self.assertEqual(PaymentAttempt.objects.count(), 0)
