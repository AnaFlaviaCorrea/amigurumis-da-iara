from decimal import Decimal

import requests
from django.conf import settings


MERCADO_PAGO_API_URL = "https://api.mercadopago.com"


def mercado_pago_configured():
    return bool(
        settings.MERCADO_PAGO_PUBLIC_KEY
        and settings.MERCADO_PAGO_ACCESS_TOKEN
    )


def _format_amount(value):
    return f"{Decimal(value):.2f}"


def _mercado_pago_request(
    method,
    path,
    *,
    payload=None,
    idempotency_key=None,
):
    headers = {
        "Authorization": (
            f"Bearer {settings.MERCADO_PAGO_ACCESS_TOKEN}"
        ),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    if idempotency_key:
        headers["X-Idempotency-Key"] = str(idempotency_key)

    response = requests.request(
        method,
        f"{MERCADO_PAGO_API_URL}{path}",
        headers=headers,
        json=payload,
        timeout=20,
    )

    try:
        data = response.json()
    except ValueError:
        data = {
            "message": (
                "O Mercado Pago devolveu uma resposta inválida."
            )
        }

    return response.status_code, data


def create_mercado_pago_order(order, attempt, form_data):
    payer_data = form_data.get("payer") or {}

    payer = {
        "email": order.email,
    }

    identification = payer_data.get("identification")

    if identification:
        payer["identification"] = {
            "type": identification.get("type", ""),
            "number": identification.get("number", ""),
        }

    payment_method = {
        "id": form_data.get("payment_method_id"),
        "type": form_data.get("payment_type_id"),
    }

    for field in ("token", "installments"):
        value = form_data.get(field)

        if value not in (None, ""):
            payment_method[field] = value

    amount = _format_amount(order.total)

    order_data = {
        "type": "online",
        "processing_mode": "automatic",
        "total_amount": amount,
        "external_reference": str(order.public_id),
        "description": (
            f"Pedido {order.short_code} - Amigurumis da Iara"
        ),
        "payer": payer,
        "transactions": {
            "payments": [
                {
                    "amount": amount,
                    "payment_method": payment_method,
                }
            ]
        },
    }

    return _mercado_pago_request(
        "POST",
        "/v1/orders",
        payload=order_data,
        idempotency_key=attempt.idempotency_key,
    )


def get_mercado_pago_order(order_id):
    return _mercado_pago_request(
        "GET",
        f"/v1/orders/{order_id}",
    )


def apply_order_response(attempt, mercado_pago_order):
    payments = (
        (mercado_pago_order.get("transactions") or {})
        .get("payments")
        or []
    )

    payment = payments[0] if payments else {}
    payment_method = payment.get("payment_method") or {}

    attempt.provider_order_id = str(
        mercado_pago_order.get("id")
        or attempt.provider_order_id
    )

    attempt.status = (
        mercado_pago_order.get("status")
        or "created"
    )

    attempt.status_detail = (
        mercado_pago_order.get("status_detail")
        or ""
    )

    attempt.provider_payment_id = str(
        payment.get("id")
        or attempt.provider_payment_id
    )

    attempt.transaction_status = (
        payment.get("status")
        or ""
    )

    attempt.transaction_status_detail = (
        payment.get("status_detail")
        or ""
    )

    attempt.payment_method_id = (
        payment_method.get("id")
        or ""
    )

    attempt.payment_type_id = (
        payment_method.get("type")
        or ""
    )

    attempt.qr_code = (
        payment_method.get("qr_code")
        or ""
    )

    attempt.qr_code_base64 = (
        payment_method.get("qr_code_base64")
        or ""
    )

    attempt.ticket_url = (
        payment_method.get("ticket_url")
        or ""
    )

    attempt.save()

    order = attempt.order

    if (
        attempt.status == "processed"
        and order.status == order.Status.PENDING
    ):
        order.status = order.Status.PAID

        order.save(
            update_fields=(
                "status",
                "updated_at",
            )
        )

    return attempt


def mercado_pago_error_message(response_data):
    errors = response_data.get("errors") or []

    messages = [
        error.get("message")
        for error in errors
        if error.get("message")
    ]

    return (
        "; ".join(messages)
        or response_data.get("message")
        or "O pagamento não pôde ser processado."
    )


def validate_mercado_pago_webhook(
    x_signature,
    x_request_id,
    data_id,
):
    if not settings.MERCADO_PAGO_WEBHOOK_SECRET:
        return False

    from mercadopago.webhook import (
        InvalidWebhookSignatureError,
        WebhookSignatureValidator,
    )

    try:
        WebhookSignatureValidator.validate(
            x_signature,
            x_request_id,
            data_id,
            settings.MERCADO_PAGO_WEBHOOK_SECRET,
        )
    except (
        InvalidWebhookSignatureError,
        TypeError,
        ValueError,
    ):
        return False

    return True