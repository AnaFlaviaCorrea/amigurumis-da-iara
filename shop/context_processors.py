def cart_summary(request):
    cart_data = request.session.get("cart", {})
    return {
        "cart_item_count": sum(item.get("quantity", 0) for item in cart_data.values())
    }
