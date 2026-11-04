import json
import logging

logger = logging.getLogger(__name__)

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from decimal import Decimal, InvalidOperation

from .cart import Cart
from .forms import CartAddForm, CheckoutForm
from .models import Category, Order, OrderItem, PaymentAttempt, Product
from .payments import (
    apply_order_response,
    create_mercado_pago_order,
    get_mercado_pago_order,
    mercado_pago_configured,
    mercado_pago_error_message,
    validate_mercado_pago_webhook,
)
from .shipping import (
    ShippingAPIError,
    ShippingConfigurationError,
    build_cart_shipping_products,
    calculate_shipping,
    normalize_postal_code,
)


def product_list(request):
    products = Product.objects.filter(active=True).select_related("category")
    categories = Category.objects.filter(active=True, products__active=True).distinct()

    category_slug = request.GET.get("categoria", "")
    product_type = request.GET.get("modalidade", "")

    if category_slug:
        products = products.filter(category__slug=category_slug)
    if product_type in Product.ProductType.values:
        products = products.filter(product_type=product_type)

    return render(
        request,
        "shop/product_list.html",
        {
            "products": products,
            "categories": categories,
            "selected_category": category_slug,
            "selected_type": product_type,
            "product_types": Product.ProductType,
        },
    )


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("images"),
        slug=slug,
        active=True,
    )
    maximum = product.stock if product.product_type == Product.ProductType.READY else 10
    cart_form = CartAddForm()
    cart_form.fields["quantity"].widget.attrs["max"] = max(maximum, 1)
    return render(
        request,
        "shop/product_detail.html",
        {"product": product, "cart_form": cart_form},
    )


def cart_detail(request):
    cart = Cart(request)
    return render(request, "shop/cart_detail.html", {"cart": cart})


def cart_add(request, product_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    product = get_object_or_404(Product, id=product_id, active=True)
    if not product.available:
        messages.error(request, "Esta peça não está disponível no momento.")
        return redirect(product.get_absolute_url())

    form = CartAddForm(request.POST)
    if form.is_valid():
        requested_quantity = form.cleaned_data["quantity"]
        cart = Cart(request)
        resulting_quantity = cart.quantity_for(product) + requested_quantity
        if (
            product.product_type == Product.ProductType.READY
            and resulting_quantity > product.stock
        ):
            messages.error(
                request, f"Temos apenas {product.stock} unidade(s) disponível(is)."
            )
            return redirect(product.get_absolute_url())

        cart.add(
            product=product,
            quantity=requested_quantity,
            replace=form.cleaned_data["replace"],
        )
        messages.success(request, f"{product.name} foi adicionado ao carrinho.")
        return redirect("shop:cart_detail")

    messages.error(request, "Escolha uma quantidade válida.")
    return redirect(product.get_absolute_url())


def cart_update(request, product_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    product = get_object_or_404(Product, id=product_id, active=True)
    form = CartAddForm(request.POST)
    if form.is_valid():
        quantity = form.cleaned_data["quantity"]
        if (
            product.product_type == Product.ProductType.READY
            and quantity > product.stock
        ):
            messages.error(
                request, f"Temos apenas {product.stock} unidade(s) disponível(is)."
            )
        else:
            Cart(request).add(product=product, quantity=quantity, replace=True)
            messages.success(request, "Quantidade atualizada.")
    else:
        messages.error(request, "Escolha uma quantidade válida.")
    return redirect("shop:cart_detail")


def cart_remove(request, product_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    product = get_object_or_404(Product, id=product_id)
    Cart(request).remove(product)
    messages.success(request, f"{product.name} foi removido do carrinho.")
    return redirect("shop:cart_detail")


@require_POST
def calculate_shipping_quotes(request):
    cart = Cart(request)

    if len(cart) == 0:
        return JsonResponse(
            {"error": "Seu carrinho está vazio."},
            status=400,
        )

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Dados de frete inválidos."},
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {"error": "Dados de frete inválidos."},
            status=400,
        )

    try:
        postal_code = normalize_postal_code(payload.get("postal_code", ""))
        products = build_cart_shipping_products(cart)
        quotes = calculate_shipping(
            postal_code,
            products,
        )
    except ValueError as error:
        return JsonResponse(
            {"error": str(error)},
            status=400,
        )
    except ShippingConfigurationError as error:
        return JsonResponse(
            {"error": str(error)},
            status=503,
        )
    except ShippingAPIError as error:
        return JsonResponse(
            {"error": str(error)},
            status=502,
        )

    serialized_quotes = [
        {
            "service_id": quote["service_id"],
            "service_name": quote["service_name"],
            "company_name": quote["company_name"],
            "price": f'{quote["price"]:.2f}',
            "delivery_time": quote["delivery_time"],
        }
        for quote in quotes
    ]

    if not serialized_quotes:
        return JsonResponse(
            {"error": ("Nenhuma opção de entrega foi encontrada " "para esse CEP.")},
            status=404,
        )

    request.session["shipping_quotes"] = serialized_quotes
    request.session["shipping_quote_postal_code"] = postal_code
    request.session.modified = True

    return JsonResponse({"quotes": serialized_quotes})


def checkout(request):
    cart = Cart(request)
    cart_items = list(cart)
    if not cart_items:
        messages.error(request, "Seu carrinho está vazio.")
        return redirect("shop:product_list")

    unavailable_items = []
    for item in cart_items:
        product = item["product"]
        if not product.available:
            unavailable_items.append(product.name)
        elif (
            product.product_type == Product.ProductType.READY
            and item["quantity"] > product.stock
        ):
            unavailable_items.append(product.name)

    if unavailable_items:
        messages.error(
            request,
            "Revise a disponibilidade antes de continuar: "
            + ", ".join(unavailable_items),
        )
        return redirect("shop:cart_detail")

    selected_shipping_service_id = ""

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        selected_shipping_service_id = request.POST.get(
            "shipping_service_id",
            "",
        )

        if form.is_valid():
            delivery_method = form.cleaned_data["delivery_method"]

            selected_quote = None
            shipping_cost = Decimal("0.00")
            shipping_calculated = delivery_method == Order.DeliveryMethod.PICKUP

            if delivery_method == Order.DeliveryMethod.SHIPPING:
                try:
                    postal_code = normalize_postal_code(
                        form.cleaned_data["postal_code"]
                    )
                except ValueError as error:
                    form.add_error(
                        "postal_code",
                        str(error),
                    )
                else:
                    quoted_postal_code = request.session.get(
                        "shipping_quote_postal_code"
                    )
                    available_quotes = request.session.get(
                        "shipping_quotes",
                        [],
                    )

                    if quoted_postal_code == postal_code:
                        selected_quote = next(
                            (
                                quote
                                for quote in available_quotes
                                if quote["service_id"] == selected_shipping_service_id
                            ),
                            None,
                        )

                    if selected_quote is None:
                        form.add_error(
                            None,
                            ("Calcule o frete e escolha " "uma opção de entrega."),
                        )
                    else:
                        try:
                            shipping_cost = Decimal(selected_quote["price"])
                        except (
                            InvalidOperation,
                            TypeError,
                            ValueError,
                        ):
                            form.add_error(
                                None,
                                ("A opção de frete escolhida " "não é válida."),
                            )
                        else:
                            if shipping_cost < 0:
                                form.add_error(
                                    None,
                                    ("A opção de frete escolhida " "não é válida."),
                                )
                            else:
                                shipping_calculated = True

            if not form.errors:
                with transaction.atomic():
                    subtotal = cart.get_subtotal()
                    order = form.save(commit=False)
                    order.subtotal = subtotal
                    order.shipping_cost = shipping_cost
                    order.shipping_calculated = shipping_calculated

                    if selected_quote is not None:
                        order.shipping_service_id = selected_quote["service_id"]
                        order.shipping_service_name = selected_quote["service_name"]
                        order.shipping_company_name = selected_quote["company_name"]
                        order.shipping_delivery_time = selected_quote["delivery_time"]

                    order.total = subtotal
                    order.save()

                    for item in cart_items:
                        product = item["product"]

                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            product_name=product.name,
                            product_type=product.product_type,
                            unit_price=item["price"],
                            quantity=item["quantity"],
                        )

                    request.session["last_order_id"] = str(order.public_id)
                    request.session.pop(
                        "shipping_quotes",
                        None,
                    )
                    request.session.pop(
                        "shipping_quote_postal_code",
                        None,
                    )
                    cart.clear()

                return redirect(
                    "shop:order_payment",
                    public_id=order.public_id,
                )
    else:
        form = CheckoutForm()

    return render(
        request,
        "shop/checkout.html",
        {
            "cart": cart,
            "cart_items": cart_items,
            "form": form,
            "selected_shipping_service_id": (selected_shipping_service_id),
        },
    )


def _session_order_or_redirect(request, public_id):
    if request.session.get("last_order_id") != str(public_id):
        return None
    return get_object_or_404(
        Order.objects.prefetch_related("items"), public_id=public_id
    )


def order_payment(request, public_id):
    order = _session_order_or_redirect(request, public_id)
    if order is None:
        return redirect("shop:product_list")
    if order.status == Order.Status.PAID:
        return redirect("shop:order_success", public_id=order.public_id)

    attempt = None
    configured = mercado_pago_configured()
    if order.payment_ready and configured:
        attempt_id = request.session.get("payment_attempt_id")
        if attempt_id:
            attempt = PaymentAttempt.objects.filter(
                public_id=attempt_id,
                order=order,
                status=PaymentAttempt.Status.CREATED,
            ).first()
        if attempt is None:
            attempt = PaymentAttempt.objects.create(order=order, amount=order.total)
            request.session["payment_attempt_id"] = str(attempt.public_id)

    return render(
        request,
        "shop/payment.html",
        {
            "order": order,
            "attempt": attempt,
            "payment_configured": configured,
            "mercado_pago_public_key": settings.MERCADO_PAGO_PUBLIC_KEY,
        },
    )


@require_POST
def process_payment(request, public_id):
    order = _session_order_or_redirect(request, public_id)
    if order is None:
        return JsonResponse(
            {"error": "Pedido não encontrado nesta sessão."}, status=403
        )
    if not order.payment_ready:
        return JsonResponse({"error": "O frete ainda não foi calculado."}, status=409)
    if not mercado_pago_configured():
        return JsonResponse(
            {"error": "O Mercado Pago ainda não foi configurado."}, status=503
        )

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Dados de pagamento inválidos."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse(
            {"error": "Dados de pagamento inválidos."},
            status=400,
        )

    payment_method_id = payload.get("payment_method_id")
    payment_type_id = payload.get("payment_type_id")

    if payment_method_id == "pix":
        payload["payment_type_id"] = "bank_transfer"

    elif payment_method_id == "boleto":
        payload["payment_type_id"] = "ticket"

        payer = payload.get("payer")

        if not isinstance(payer, dict):
            payer = {}

        payload["payer"] = payer

        identification = payer.get("identification")

        if not isinstance(identification, dict):
            identification = {}

        cpf = "".join(
            character
            for character in str(identification.get("number", ""))
            if character.isdigit()
        )

        if identification.get("type") != "CPF" or len(cpf) != 11:
            return JsonResponse(
                {"error": ("Informe um CPF válido " "para gerar o boleto.")},
                status=400,
            )

        payer["identification"] = {
            "type": "CPF",
            "number": cpf,
        }

        if order.delivery_method == Order.DeliveryMethod.SHIPPING:
            payer["address"] = {
                "zip_code": order.postal_code,
                "street_name": order.street,
                "street_number": order.number,
                "neighborhood": order.neighborhood,
                "city": order.city,
                "state": order.state,
            }

        address = payer.get("address")

        if not isinstance(address, dict):
            address = {}

        required_address_fields = {
            "zip_code": "CEP",
            "street_name": "rua",
            "street_number": "número",
            "neighborhood": "bairro",
            "city": "cidade",
            "state": "estado",
        }

        missing_fields = [
            label
            for field, label in required_address_fields.items()
            if not str(address.get(field, "")).strip()
        ]

        if missing_fields:
            return JsonResponse(
                {
                    "error": (
                        "Informe os seguintes dados para "
                        "gerar o boleto: " + ", ".join(missing_fields) + "."
                    )
                },
                status=400,
            )

        state = str(address.get("state", "")).strip()

        if len(state) != 2:
            return JsonResponse(
                {"error": ("Informe o estado utilizando " "duas letras, como SC.")},
                status=400,
            )

    elif payment_type_id not in {
        "credit_card",
        "debit_card",
        "prepaid_card",
    }:
        return JsonResponse(
            {"error": "Forma de pagamento inválida."},
            status=400,
        )
    attempt = get_object_or_404(
        PaymentAttempt,
        public_id=payload.pop("attempt_id", None),
        order=order,
        status=PaymentAttempt.Status.CREATED,
    )
    try:
        http_status, mercado_pago_order = create_mercado_pago_order(
            order,
            attempt,
            payload,
        )
    except Exception:
        logger.exception(
            "Erro ao criar order no Mercado Pago para o pedido %s",
            order.public_id,
        )

        return JsonResponse(
            {
                "error": (
                    "Não foi possível comunicar com o Mercado Pago. "
                    "Consulte o terminal."
                )
            },
            status=502,
        )

    if http_status in (200, 201):
        order_response = mercado_pago_order
    elif http_status == 402:
        order_response = mercado_pago_order.get("data") or {}
    else:
        message = mercado_pago_error_message(mercado_pago_order)
        return JsonResponse(
            {"error": message},
            status=400,
        )
    if not order_response.get("id"):
        message = mercado_pago_error_message(mercado_pago_order)
        return JsonResponse(
            {"error": message},
            status=400,
        )

    apply_order_response(
        attempt,
        order_response,
    )

    request.session["last_payment_attempt_id"] = str(attempt.public_id)
    request.session.pop("payment_attempt_id", None)
    return JsonResponse(
        {
            "status": attempt.status,
            "redirect_url": reverse(
                "shop:payment_result",
                kwargs={"public_id": order.public_id, "attempt_id": attempt.public_id},
            ),
        }
    )


def payment_result(request, public_id, attempt_id):
    order = _session_order_or_redirect(request, public_id)
    if order is None:
        return redirect("shop:product_list")
    if request.session.get("last_payment_attempt_id") != str(attempt_id):
        return redirect("shop:order_payment", public_id=order.public_id)
    attempt = get_object_or_404(PaymentAttempt, public_id=attempt_id, order=order)
    return render(
        request, "shop/payment_result.html", {"order": order, "attempt": attempt}
    )


@csrf_exempt
@require_POST
def mercado_pago_webhook(request):
    data_id = request.GET.get("data.id") or request.GET.get("id")

    if not data_id:
        try:
            body = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            body = {}

        data_id = str((body.get("data") or {}).get("id") or "")

    if not data_id:
        return HttpResponse(status=400)

    signature_is_valid = validate_mercado_pago_webhook(
        request.headers.get("x-signature"),
        request.headers.get("x-request-id"),
        data_id,
    )

    if not signature_is_valid:
        return HttpResponse(status=401)

    attempt = PaymentAttempt.objects.filter(provider_order_id=str(data_id)).first()

    # A notificação pode pertencer a uma order que não está
    # registrada neste banco. Confirmamos o recebimento para
    # evitar que o Mercado Pago continue reenviando.
    if attempt is None:
        return HttpResponse(status=200)

    try:
        http_status, mercado_pago_order = get_mercado_pago_order(data_id)
    except Exception:
        logger.exception(
            "Erro ao consultar a order %s no webhook",
            data_id,
        )
        return HttpResponse(status=503)

    if http_status != 200:
        logger.warning(
            "Mercado Pago devolveu status %s ao consultar " "a order %s no webhook",
            http_status,
            data_id,
        )
        return HttpResponse(status=503)

    apply_order_response(
        attempt,
        mercado_pago_order,
    )

    return HttpResponse(status=200)


def order_success(request, public_id):
    order = _session_order_or_redirect(request, public_id)
    if order is None:
        return redirect("shop:product_list")
    return render(request, "shop/order_success.html", {"order": order})
