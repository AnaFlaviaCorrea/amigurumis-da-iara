from django.contrib import messages
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from .cart import Cart
from .forms import CartAddForm
from .models import Category, Product


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
        if product.product_type == Product.ProductType.READY and resulting_quantity > product.stock:
            messages.error(request, f"Temos apenas {product.stock} unidade(s) disponível(is).")
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
        if product.product_type == Product.ProductType.READY and quantity > product.stock:
            messages.error(request, f"Temos apenas {product.stock} unidade(s) disponível(is).")
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
