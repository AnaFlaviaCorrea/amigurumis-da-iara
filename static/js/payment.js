(() => {
    const container = document.getElementById(
        "cardPaymentBrick_container"
    );

    if (!container) {
        return;
    }

    const message = document.getElementById("payment-message");
    const cardPanel = document.getElementById("card-payment-panel");
    const pixPanel = document.getElementById("pix-payment-panel");
    const pixButton = document.getElementById("pix-payment-button");
    const methodButtons = document.querySelectorAll(
        "[data-payment-target]"
    );

    const csrfToken = (
        document.querySelector("[name=csrfmiddlewaretoken]")?.value
        || document.cookie
            .split("; ")
            .find(row => row.startsWith("csrftoken="))
            ?.split("=")[1]
    );

    const showError = (text) => {
        message.textContent = text;
        message.hidden = false;
    };

    const processPayment = async (payload) => {
        const response = await fetch(
            container.dataset.processUrl,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({
                    ...payload,
                    attempt_id: container.dataset.attemptId,
                }),
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error
                || "Não foi possível processar o pagamento."
            );
        }

        window.location.assign(data.redirect_url);
    };

    methodButtons.forEach(button => {
        button.addEventListener("click", () => {
            const selectedMethod = button.dataset.paymentTarget;
            const isCard = selectedMethod === "card";

            cardPanel.hidden = !isCard;
            pixPanel.hidden = isCard;
            message.hidden = true;

            methodButtons.forEach(option => {
                const isSelected = option === button;

                option.classList.toggle(
                    "is-active",
                    isSelected
                );
                option.setAttribute(
                    "aria-pressed",
                    String(isSelected)
                );
            });
        });
    });

    pixButton?.addEventListener("click", async () => {
        const originalText = pixButton.textContent;

        message.hidden = true;
        pixButton.disabled = true;
        pixButton.textContent = "Gerando Pix...";

        try {
            await processPayment({
                payment_method_id: "pix",
                payment_type_id: "bank_transfer",
                payer: {
                    email: container.dataset.payerEmail,
                },
            });
        } catch (error) {
            showError(error.message);
            pixButton.disabled = false;
            pixButton.textContent = originalText;
        }
    });

    if (typeof MercadoPago === "undefined") {
        showError(
            "Não foi possível carregar o formulário de cartão."
        );
        return;
    }

    const mercadoPago = new MercadoPago(
        container.dataset.publicKey,
        {
            locale: "pt-BR",
        }
    );

    const bricksBuilder = mercadoPago.bricks();

    const renderCardPaymentBrick = async () => {
        const settings = {
            initialization: {
                amount: Number(
                    container.dataset.amount.replace(",", ".")
                ),
                payer: {
                    email: container.dataset.payerEmail,
                },
            },

            callbacks: {
                onReady: () => {
                    message.hidden = true;
                },

                onSubmit: (formData, additionalData) => {
                    const paymentTypeId =
                        additionalData?.paymentTypeId;

                    if (!paymentTypeId) {
                        const error = new Error(
                            "Não foi possível identificar "
                            + "o tipo do cartão."
                        );

                        showError(error.message);
                        return Promise.reject(error);
                    }

                    return processPayment({
                        ...formData,
                        payment_type_id: paymentTypeId,
                    }).catch(error => {
                        showError(error.message);
                        throw error;
                    });
                },

                onError: () => {
                    showError(
                        "O formulário de cartão encontrou "
                        + "um erro. Atualize a página "
                        + "e tente novamente."
                    );
                },
            },
        };

        window.cardPaymentBrickController =
            await bricksBuilder.create(
                "cardPayment",
                "cardPaymentBrick_container",
                settings
            );
    };

    renderCardPaymentBrick().catch(() => {
        showError(
            "Não foi possível carregar "
            + "o formulário de cartão."
        );
    });

    window.addEventListener("pagehide", () => {
        window.cardPaymentBrickController?.unmount();
    });
})();