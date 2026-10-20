from decimal import Decimal

from django.conf import settings


FINAL_PAYMENT_STATUSES = {"approved", "rejected", "cancelled", "refunded"}


def mercado_pago_configured():
    return bool(settings.MERCADO_PAGO_PUBLIC_KEY and settings.MERCADO_PAGO_ACCESS_TOKEN)


def create_mercado_pago_payment(order, attempt, form_data):
    import mercadopago

    sdk = mercadopago.SDK(settings.MERCADO_PAGO_ACCESS_TOKEN)
    request_options = mercadopago.config.RequestOptions()
    request_options.custom_headers = {
        "x-idempotency-key": str(attempt.idempotency_key),
    }

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

    payment_data = {
        "transaction_amount": float(Decimal(order.total)),
        "description": f"Pedido {order.short_code} - Amigurumis da Iara",
        "external_reference": str(order.public_id),
        "payment_method_id": form_data.get("payment_method_id"),
        "payer": payer,
    }

    for field in ("token", "installments", "issuer_id"):
        value = form_data.get(field)
        if value not in (None, ""):
            payment_data[field] = value

    response = sdk.payment().create(payment_data, request_options)
    return response.get("status"), response.get("response", {})


def get_mercado_pago_payment(payment_id):
    import mercadopago

    sdk = mercadopago.SDK(settings.MERCADO_PAGO_ACCESS_TOKEN)
    response = sdk.payment().get(payment_id)
    return response.get("status"), response.get("response", {})


def apply_payment_response(attempt, payment):
    attempt.provider_payment_id = str(payment.get("id") or attempt.provider_payment_id)
    attempt.status = payment.get("status") or "created"
    attempt.status_detail = payment.get("status_detail") or ""
    attempt.payment_method_id = payment.get("payment_method_id") or ""
    attempt.payment_type_id = payment.get("payment_type_id") or ""

    transaction_data = (payment.get("point_of_interaction") or {}).get("transaction_data") or {}
    attempt.qr_code = transaction_data.get("qr_code") or ""
    attempt.qr_code_base64 = transaction_data.get("qr_code_base64") or ""
    attempt.ticket_url = transaction_data.get("ticket_url") or ""
    attempt.save()

    order = attempt.order
    if attempt.status == "approved" and order.status == order.Status.PENDING:
        order.status = order.Status.PAID
        order.save(update_fields=("status", "total", "updated_at"))
    return attempt


def validate_mercado_pago_webhook(x_signature, x_request_id, data_id):
    if not settings.MERCADO_PAGO_WEBHOOK_SECRET:
        return False

    from mercadopago.webhook import InvalidWebhookSignatureError, WebhookSignatureValidator

    try:
        WebhookSignatureValidator.validate(
            x_signature,
            x_request_id,
            data_id,
            settings.MERCADO_PAGO_WEBHOOK_SECRET,
        )
    except (InvalidWebhookSignatureError, TypeError, ValueError):
        return False
    return True
