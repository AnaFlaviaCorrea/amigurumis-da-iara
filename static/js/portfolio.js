const galleryImages = document.querySelectorAll(".gallery-lightbox-img");
const lightbox = document.getElementById("portfolioLightbox");
const lightboxImage = document.getElementById("lightboxImage");
const lightboxTitle = document.getElementById("lightboxTitle");
const lightboxSubtitle = document.getElementById("lightboxSubtitle");
const lightboxClose = document.querySelector(".lightbox-close");

galleryImages.forEach((image) => {
    image.addEventListener("click", () => {
        lightboxImage.src = image.src;
        lightboxImage.alt = image.alt;

        lightboxTitle.textContent = image.dataset.title || "";
        lightboxSubtitle.textContent = image.dataset.subtitle || "";

        lightbox.classList.add("active");
        document.body.style.overflow = "hidden";
    });
});

function closeLightbox() {
    lightbox.classList.remove("active");
    document.body.style.overflow = "";
}

lightboxClose.addEventListener("click", closeLightbox);

lightbox.addEventListener("click", (event) => {
    if (event.target === lightbox) {
        closeLightbox();
    }
});

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && lightbox.classList.contains("active")) {
        closeLightbox();
    }
});
const showMoreButtons = document.querySelectorAll(".show-more-btn");

showMoreButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const category = button.closest(".portfolio-category");

        category.classList.toggle("expanded");

        if (category.classList.contains("expanded")) {
            button.textContent = "Mostrar menos";
        } else {
            if (category.id === "pets") {
                button.textContent = "Ver todas as fotos de Pets";
            } else if (category.id === "santinhas") {
                button.textContent = "Ver todas as fotos de Arte Sacra";
            } else if (category.id === "bonecas") {
                button.textContent = "Ver todas as fotos de Bonecas";
            } else if (category.id === "personalizados") {
                button.textContent = "Ver todas as fotos de Projetos Especiais";
            } else {
                button.textContent = "Ver todas as fotos";
            }
        }
    });
});