from django.shortcuts import get_object_or_404, render

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
    return render(request, "shop/product_detail.html", {"product": product})
