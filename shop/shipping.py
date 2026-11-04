from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings

CALCULATE_SHIPPING_PATH = "/api/v2/me/shipment/calculate"


class ShippingConfigurationError(Exception):
    """Erro nas configurações da integração de frete."""


class ShippingAPIError(Exception):
    """Erro ao consultar a API do Melhor Envio."""


def melhor_envio_configured():
    return bool(
        settings.MELHOR_ENVIO_BASE_URL
        and settings.MELHOR_ENVIO_ACCESS_TOKEN
        and settings.MELHOR_ENVIO_ORIGIN_POSTAL_CODE
        and settings.MELHOR_ENVIO_USER_AGENT
    )


def normalize_postal_code(value):
    postal_code = "".join(character for character in str(value) if character.isdigit())

    if len(postal_code) != 8:
        raise ValueError("Informe um CEP válido com 8 números.")

    return postal_code


def build_cart_shipping_products(cart):
    shipping_products = []

    for item in cart:
        product = item["product"]
        profile = product.shipping_profile

        if profile is None or not profile.active:
            raise ShippingConfigurationError(
                (f'O produto "{product.name}" não possui ' "um perfil de envio ativo.")
            )

        shipping_products.append(
            {
                "id": str(product.id),
                "width": profile.width,
                "height": profile.height,
                "length": profile.length,
                "weight": float(profile.weight),
                "insurance_value": float(item["price"]),
                "quantity": item["quantity"],
            }
        )

    if not shipping_products:
        raise ValueError("O carrinho não possui produtos para envio.")

    return shipping_products


def calculate_shipping(destination_postal_code, products):
    if not melhor_envio_configured():
        raise ShippingConfigurationError("O Melhor Envio ainda não foi configurado.")

    origin_postal_code = normalize_postal_code(settings.MELHOR_ENVIO_ORIGIN_POSTAL_CODE)
    destination_postal_code = normalize_postal_code(destination_postal_code)

    if not products:
        raise ValueError("É necessário informar ao menos um produto.")

    payload = {
        "from": {
            "postal_code": origin_postal_code,
        },
        "to": {
            "postal_code": destination_postal_code,
        },
        "products": products,
    }

    headers = {
        "Authorization": (f"Bearer {settings.MELHOR_ENVIO_ACCESS_TOKEN}"),
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": settings.MELHOR_ENVIO_USER_AGENT,
    }

    try:
        response = requests.post(
            (f"{settings.MELHOR_ENVIO_BASE_URL}" f"{CALCULATE_SHIPPING_PATH}"),
            headers=headers,
            json=payload,
            timeout=20,
        )
    except requests.RequestException as error:
        raise ShippingAPIError(
            "Não foi possível comunicar com o Melhor Envio."
        ) from error

    try:
        response_data = response.json()
    except ValueError as error:
        raise ShippingAPIError(
            "O Melhor Envio devolveu uma resposta inválida."
        ) from error

    if not response.ok:
        if isinstance(response_data, dict):
            message = response_data.get("message") or response_data.get("error")
        else:
            message = None

        raise ShippingAPIError(message or "Não foi possível calcular o frete.")

    if not isinstance(response_data, list):
        raise ShippingAPIError("O Melhor Envio devolveu um formato inesperado.")

    quotes = []

    for option in response_data:
        if option.get("error"):
            continue

        raw_price = option.get("custom_price") or option.get("price")

        if raw_price in (None, ""):
            continue

        try:
            price = Decimal(str(raw_price))
        except (InvalidOperation, TypeError, ValueError):
            continue

        raw_delivery_time = option.get("custom_delivery_time")

        if raw_delivery_time is None:
            raw_delivery_time = option.get(
                "delivery_time",
                0,
            )

        company = option.get("company") or {}

        quotes.append(
            {
                "service_id": str(option.get("id", "")),
                "service_name": option.get("name", ""),
                "company_name": company.get("name", ""),
                "price": price,
                "delivery_time": int(raw_delivery_time or 0),
            }
        )

    return quotes
