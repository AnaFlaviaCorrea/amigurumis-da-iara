from django.contrib import admin

from .models import Category, Order, OrderItem, PaymentAttempt, Product, ProductImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "active")
    list_filter = ("active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "product_type",
        "price",
        "stock",
        "active",
        "featured",
    )
    list_editable = ("price", "stock", "active", "featured")
    list_filter = ("product_type", "category", "active", "featured")
    search_fields = ("name", "short_description", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("portfolio_source", "portfolio_hash")
    inlines = (ProductImageInline,)


admin.site.site_header = "Amigurumis da Iara"
admin.site.site_title = "Administração da loja"
admin.site.index_title = "Produtos e pedidos"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "product_name", "product_type", "unit_price", "quantity")


class PaymentAttemptInline(admin.TabularInline):
    model = PaymentAttempt
    extra = 0
    can_delete = False
    readonly_fields = (
        "public_id",
        "provider_payment_id",
        "status",
        "status_detail",
        "payment_method_id",
        "payment_type_id",
        "amount",
        "created_at",
        "updated_at",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("short_code", "full_name", "status", "delivery_method", "total", "created_at")
    list_filter = ("status", "delivery_method", "created_at")
    search_fields = ("public_id", "full_name", "email", "phone")
    readonly_fields = ("public_id", "subtotal", "shipping_cost", "total", "created_at", "updated_at")
    inlines = (OrderItemInline, PaymentAttemptInline)


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ("public_id", "order", "status", "payment_method_id", "amount", "created_at")
    list_filter = ("status", "payment_type_id", "created_at")
    search_fields = ("public_id", "provider_payment_id", "order__public_id", "order__email")
    readonly_fields = (
        "public_id",
        "idempotency_key",
        "provider_payment_id",
        "created_at",
        "updated_at",
    )
