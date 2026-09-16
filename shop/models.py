from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField("nome", max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    active = models.BooleanField("ativa", default=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "categoria"
        verbose_name_plural = "categorias"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    class ProductType(models.TextChoices):
        READY = "ready", "Pronta entrega"
        MADE_TO_ORDER = "made_to_order", "Sob encomenda"

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="categoria",
    )
    name = models.CharField("nome", max_length=140)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    short_description = models.CharField("descrição curta", max_length=220)
    description = models.TextField("descrição")
    price = models.DecimalField("preço", max_digits=10, decimal_places=2)
    product_type = models.CharField(
        "modalidade",
        max_length=20,
        choices=ProductType.choices,
        default=ProductType.READY,
    )
    stock = models.PositiveIntegerField("estoque", default=0)
    production_days = models.PositiveIntegerField(
        "prazo de produção em dias",
        null=True,
        blank=True,
        help_text="Preencha apenas para produtos sob encomenda.",
    )
    customizable = models.BooleanField("permite personalização", default=False)
    main_image = models.ImageField("imagem principal", upload_to="products/%Y/%m/")
    active = models.BooleanField("ativo", default=True)
    featured = models.BooleanField("destaque", default=False)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ("-featured", "name")
        verbose_name = "produto"
        verbose_name_plural = "produtos"

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}
        if self.price <= 0:
            errors["price"] = "O preço deve ser maior que zero."
        if self.product_type == self.ProductType.MADE_TO_ORDER and not self.production_days:
            errors["production_days"] = "Informe o prazo para produzir a encomenda."
        if self.product_type == self.ProductType.READY and self.production_days:
            errors["production_days"] = "Produtos à pronta entrega não precisam de prazo de produção."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 2
            while Product.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("shop:product_detail", kwargs={"slug": self.slug})

    @property
    def available(self):
        return self.product_type == self.ProductType.MADE_TO_ORDER or self.stock > 0


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="produto",
    )
    image = models.ImageField("imagem", upload_to="products/%Y/%m/")
    alt_text = models.CharField("texto alternativo", max_length=180, blank=True)
    order = models.PositiveSmallIntegerField("ordem", default=0)

    class Meta:
        ordering = ("order", "id")
        verbose_name = "imagem do produto"
        verbose_name_plural = "imagens do produto"

    def __str__(self):
        return f"Imagem de {self.product.name}"
