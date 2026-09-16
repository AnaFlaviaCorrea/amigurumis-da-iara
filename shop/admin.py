from django.contrib import admin

from .models import Category, Product, ProductImage


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
    inlines = (ProductImageInline,)


admin.site.site_header = "Amigurumis da Iara"
admin.site.site_title = "Administração da loja"
admin.site.index_title = "Produtos e pedidos"
