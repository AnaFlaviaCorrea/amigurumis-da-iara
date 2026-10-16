from django.contrib import admin

from .models import Category, Order, OrderItem, Product, ProductImage


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


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("short_code", "full_name", "status", "delivery_method", "total", "created_at")
    list_filter = ("status", "delivery_method", "created_at")
    search_fields = ("public_id", "full_name", "email", "phone")
    readonly_fields = ("public_id", "subtotal", "shipping_cost", "total", "created_at", "updated_at")
    inlines = (OrderItemInline,)
