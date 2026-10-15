import hashlib
import re
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from shop.models import Category, Product


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

CATEGORY_NAMES = {
    "bonecas": "Bonecas",
    "pets": "Pets realistas",
    "santinhas": "Arte Sacra",
    "personalizados": "Personalizados",
}


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as image_file:
        for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_name(path):
    name = re.sub(r"[_-]+", " ", path.stem)
    name = re.sub(r"(?<=\D)(\d+)$", r" \1", name)
    return " ".join(word.capitalize() for word in name.split())


class Command(BaseCommand):
    help = "Importa imagens do portfólio como produtos inativos da loja."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            type=Path,
            help="Pasta do portfólio. Por padrão usa static/img/portfolio.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria feito sem alterar o banco ou copiar imagens.",
        )

    def handle(self, *args, **options):
        source_root = options["source"] or Path(settings.BASE_DIR) / "static" / "img" / "portfolio"
        source_root = source_root.resolve()

        if not source_root.is_dir():
            raise CommandError(f"Pasta do portfólio não encontrada: {source_root}")

        image_paths = sorted(
            path
            for path in source_root.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )

        if not image_paths:
            self.stdout.write(self.style.WARNING("Nenhuma imagem compatível foi encontrada."))
            return

        counters = {"created": 0, "updated": 0, "renamed": 0, "skipped": 0}

        for image_path in image_paths:
            relative_path = image_path.relative_to(source_root).as_posix()
            image_digest = file_hash(image_path)

            existing = Product.objects.filter(portfolio_source=relative_path).first()
            if existing:
                if existing.portfolio_hash == image_digest:
                    counters["skipped"] += 1
                    self.stdout.write(f"IGNORADA (já importada): {relative_path}")
                    continue

                counters["updated"] += 1
                self.stdout.write(f"ATUALIZAR imagem: {relative_path}")
                if not options["dry_run"]:
                    self._replace_image(existing, image_path, image_digest)
                continue

            same_image = Product.objects.filter(portfolio_hash=image_digest).first()
            if same_image:
                counters["renamed"] += 1
                self.stdout.write(
                    f"RENOMEADA: {same_image.portfolio_source} -> {relative_path}"
                )
                if not options["dry_run"]:
                    same_image.portfolio_source = relative_path
                    same_image.save(update_fields=("portfolio_source", "updated_at"))
                continue

            counters["created"] += 1
            self.stdout.write(f"NOVA: {relative_path}")
            if not options["dry_run"]:
                self._create_product(source_root, image_path, relative_path, image_digest)

        label = "SIMULAÇÃO" if options["dry_run"] else "IMPORTAÇÃO CONCLUÍDA"
        self.stdout.write(
            self.style.SUCCESS(
                f"{label}: {counters['created']} nova(s), "
                f"{counters['updated']} atualizada(s), "
                f"{counters['renamed']} renomeada(s) e "
                f"{counters['skipped']} já importada(s)."
            )
        )

    @transaction.atomic
    def _create_product(self, source_root, image_path, relative_path, image_digest):
        relative = image_path.relative_to(source_root)
        folder_name = relative.parts[0] if len(relative.parts) > 1 else "outros"
        category_name = CATEGORY_NAMES.get(folder_name.lower(), folder_name.replace("_", " ").title())
        category, _ = Category.objects.get_or_create(name=category_name)

        product = Product(
            category=category,
            name=display_name(image_path),
            short_description="Peça artesanal do portfólio da Iara.",
            description=(
                "Imagem importada do portfólio. Revise o nome, a descrição, "
                "o preço, o prazo e as opções de personalização antes de ativar."
            ),
            price=None,
            product_type=Product.ProductType.MADE_TO_ORDER,
            stock=0,
            production_days=30,
            customizable=True,
            active=False,
            portfolio_source=relative_path,
            portfolio_hash=image_digest,
        )
        with image_path.open("rb") as image_file:
            product.main_image.save(image_path.name, File(image_file), save=False)
        product.save()

    @transaction.atomic
    def _replace_image(self, product, image_path, image_digest):
        old_image = product.main_image
        with image_path.open("rb") as image_file:
            product.main_image.save(image_path.name, File(image_file), save=False)
        product.portfolio_hash = image_digest
        product.save(update_fields=("main_image", "portfolio_hash", "updated_at"))
        if old_image and old_image.name != product.main_image.name:
            old_image.delete(save=False)
