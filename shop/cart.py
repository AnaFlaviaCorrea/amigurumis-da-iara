from decimal import Decimal

from .models import Product


class Cart:
    SESSION_KEY = "cart"

    def __init__(self, request):
        self.session = request.session
        self.cart = self.session.get(self.SESSION_KEY, {})

    def add(self, product, quantity=1, replace=False):
        product_id = str(product.id)
        current_quantity = self.cart.get(product_id, {}).get("quantity", 0)
        new_quantity = quantity if replace else current_quantity + quantity

        if product.product_type == Product.ProductType.READY:
            new_quantity = min(new_quantity, product.stock)

        if new_quantity <= 0:
            self.remove(product)
            return

        self.cart[product_id] = {"quantity": new_quantity}
        self.save()

    def remove(self, product):
        product_id = str(product.id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def quantity_for(self, product):
        return self.cart.get(str(product.id), {}).get("quantity", 0)

    def save(self):
        self.session[self.SESSION_KEY] = self.cart
        self.session.modified = True

    def clear(self):
        self.session.pop(self.SESSION_KEY, None)
        self.session.modified = True

    def __iter__(self):
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids, active=True).select_related("category")

        cart = self.cart.copy()
        valid_ids = set()
        for product in products:
            product_id = str(product.id)
            valid_ids.add(product_id)
            item = cart[product_id].copy()
            item["product"] = product
            item["price"] = product.price
            item["total_price"] = product.price * item["quantity"]
            yield item

        stale_ids = set(cart) - valid_ids
        if stale_ids:
            for product_id in stale_ids:
                self.cart.pop(product_id, None)
            self.save()

    def __len__(self):
        return sum(item["quantity"] for item in self.cart.values())

    def get_subtotal(self):
        return sum((item["total_price"] for item in self), Decimal("0.00"))
