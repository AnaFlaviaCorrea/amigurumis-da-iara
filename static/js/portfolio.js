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
    const originalText = button.textContent;

    button.addEventListener("click", () => {
        const category = button.closest(".portfolio-category");

        category.classList.toggle("expanded");

        if (category.classList.contains("expanded")) {
            button.textContent = "Mostrar menos";
        } else {
            button.textContent = originalText;
        }
    });
});