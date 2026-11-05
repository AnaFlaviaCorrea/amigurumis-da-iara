from datetime import timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

from .models import MelhorEnvioCredential

CALCULATE_SHIPPING_PATH = "/api/v2/me/shipment/calculate"


class ShippingConfigurationError(Exception):
    """Erro nas configurações da integração de frete."""


class ShippingAPIError(Exception):
    """Erro ao consultar a API do Melhor Envio."""


class ShippingOAuthError(Exception):
    """Erro durante a autenticação do Melhor Envio."""


def melhor_envio_oauth_configured():
    return bool(
        settings.MELHOR_ENVIO_BASE_URL
        and settings.MELHOR_ENVIO_CLIENT_ID
        and settings.MELHOR_ENVIO_CLIENT_SECRET
        and settings.MELHOR_ENVIO_REDIRECT_URI
    )


def build_authorization_url(state):
    if not melhor_envio_oauth_configured():
        raise ShippingConfigurationError("O OAuth do Melhor Envio não foi configurado.")

    parameters = {
        "client_id": settings.MELHOR_ENVIO_CLIENT_ID,
        "redirect_uri": (settings.MELHOR_ENVIO_REDIRECT_URI),
        "response_type": "code",
        "state": state,
        "scope": "shipping-calculate",
    }

    return (
        f"{settings.MELHOR_ENVIO_BASE_URL}" f"/oauth/authorize?{urlencode(parameters)}"
    )


def exchange_authorization_code(code):
    if not melhor_envio_oauth_configured():
        raise ShippingConfigurationError("O OAuth do Melhor Envio não foi configurado.")

    try:
        response = requests.post(
            (f"{settings.MELHOR_ENVIO_BASE_URL}" "/oauth/token"),
            data={
                "grant_type": "authorization_code",
                "client_id": (settings.MELHOR_ENVIO_CLIENT_ID),
                "client_secret": (settings.MELHOR_ENVIO_CLIENT_SECRET),
                "redirect_uri": (settings.MELHOR_ENVIO_REDIRECT_URI),
                "code": code,
            },
            headers={
                "Accept": "application/json",
            },
            timeout=20,
        )
    except requests.RequestException as error:
        raise ShippingOAuthError(
            "Não foi possível autenticar no Melhor Envio."
        ) from error

    try:
        response_data = response.json()
    except ValueError as error:
        raise ShippingOAuthError(
            "O Melhor Envio devolveu uma resposta inválida."
        ) from error

    if not response.ok:
        message = (
            response_data.get("message")
            or response_data.get("error_description")
            or response_data.get("error")
            or "Não foi possível concluir a autorização."
        )

        raise ShippingOAuthError(message)

    access_token = response_data.get("access_token")
    refresh_token = response_data.get("refresh_token")

    if not access_token or not refresh_token:
        raise ShippingOAuthError("O Melhor Envio não devolveu os tokens esperados.")

    expires_in = response_data.get("expires_in")
    expires_at = None

    if expires_in is not None:
        try:
            expires_at = timezone.now() + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            expires_at = None

    scope = response_data.get(
        "scope",
        "shipping-calculate",
    )

    if isinstance(scope, list):
        scope = " ".join(scope)

    credential, _ = MelhorEnvioCredential.objects.update_or_create(
        pk=1,
        defaults={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": response_data.get(
                "token_type",
                "Bearer",
            ),
            "scope": str(scope),
            "expires_at": expires_at,
        },
    )

    return credential


def get_melhor_envio_access_token():
    if settings.MELHOR_ENVIO_ACCESS_TOKEN:
        return settings.MELHOR_ENVIO_ACCESS_TOKEN

    return (
        MelhorEnvioCredential.objects.filter(pk=1)
        .values_list("access_token", flat=True)
        .first()
        or ""
    )


def melhor_envio_configured():
    return bool(
        settings.MELHOR_ENVIO_BASE_URL
        and get_melhor_envio_access_token()
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
    access_token = get_melhor_envio_access_token()
    headers = {
        "Authorization": (f"Bearer {access_token}"),
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
