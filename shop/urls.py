from django.urls import path

from . import views

app_name = "shop"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("carrinho/", views.cart_detail, name="cart_detail"),
    path("carrinho/adicionar/<int:product_id>/", views.cart_add, name="cart_add"),
    path("carrinho/atualizar/<int:product_id>/", views.cart_update, name="cart_update"),
    path("carrinho/remover/<int:product_id>/", views.cart_remove, name="cart_remove"),
    path("finalizar/", views.checkout, name="checkout"),
    path("pedido/<uuid:public_id>/confirmado/", views.order_success, name="order_success"),
    path("produto/<slug:slug>/", views.product_detail, name="product_detail"),
]
