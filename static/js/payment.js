(() => {
    const container = document.getElementById(
        "cardPaymentBrick_container"
    );

    if (!container) {
        return;
    }

    const message = document.getElementById("payment-message");
    const pixButton = document.getElementById(
        "pix-payment-button"
    );
    const boletoButton = document.getElementById(
        "boleto-payment-button"
    );
    const methodButtons = document.querySelectorAll(
        "[data-payment-target]"
    );

    const panels = {
        card: document.getElementById("card-payment-panel"),
        pix: document.getElementById("pix-payment-panel"),
        boleto: document.getElementById(
            "boleto-payment-panel"
        ),
    };

    const csrfToken = (
        document.querySelector(
            "[name=csrfmiddlewaretoken]"
        )?.value
        || document.cookie
            .split("; ")
            .find(row => row.startsWith("csrftoken="))
            ?.split("=")[1]
    );

    const showError = (text) => {
        message.textContent = text;
        message.hidden = false;
    };

    const hideMessage = () => {
        message.hidden = true;
        message.textContent = "";
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

    let cardRenderPromise = null;

    const renderCardPaymentBrick = async () => {
        if (typeof MercadoPago === "undefined") {
            throw new Error(
                "Não foi possível carregar "
                + "o formulário de cartão."
            );
        }

        const mercadoPago = new MercadoPago(
            container.dataset.publicKey,
            {
                locale: "pt-BR",
            }
        );

        const bricksBuilder = mercadoPago.bricks();

        const settings = {
            initialization: {
                amount: Number(
                    container.dataset.amount.replace(",", ".")
                ),
                payer: {
                    email: container.dataset.payerEmail,
                },
            },

            customization: {
                visual: {
                    style: {
                        theme: "flat",
                        customVariables: {
                            baseColor: "#B98C4A",
                            baseColorFirstVariant: "#9C733B",
                            baseColorSecondVariant: "#D7B47D",
                            buttonTextColor: "#FFFFFF",
                            textPrimaryColor: "#5B3A2E",
                            textSecondaryColor: "#7A675F",
                            formBackgroundColor: "#FFFDFC",
                            inputBackgroundColor: "#F8F5F0",
                            outlinePrimaryColor: "#D7B47D",
                            borderRadiusSmall: "8px",
                            borderRadiusMedium: "14px",
                            borderRadiusLarge: "20px",
                        },
                    },
                },
            },

            callbacks: {
                onReady: () => {
                    hideMessage();
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

    const ensureCardPaymentBrick = () => {
        if (window.cardPaymentBrickController) {
            return Promise.resolve();
        }

        if (!cardRenderPromise) {
            cardRenderPromise = renderCardPaymentBrick()
                .catch(error => {
                    cardRenderPromise = null;
                    throw error;
                });
        }

        return cardRenderPromise;
    };

    methodButtons.forEach(button => {
        button.addEventListener("click", async () => {
            const selectedMethod =
                button.dataset.paymentTarget;
            const shouldOpen = !button.classList.contains(
                "is-active"
            );

            hideMessage();

            methodButtons.forEach(option => {
                option.classList.remove("is-active");
                option.setAttribute(
                    "aria-expanded",
                    "false"
                );
            });

            Object.values(panels).forEach(panel => {
                if (panel) {
                    panel.hidden = true;
                }
            });

            if (!shouldOpen) {
                return;
            }

            button.classList.add("is-active");
            button.setAttribute("aria-expanded", "true");

            const selectedPanel = panels[selectedMethod];

            if (selectedPanel) {
                selectedPanel.hidden = false;
            }

            if (selectedMethod === "card") {
                try {
                    await ensureCardPaymentBrick();
                } catch (error) {
                    showError(error.message);
                }
            }
        });
    });

    pixButton?.addEventListener("click", async () => {
        const originalText = pixButton.textContent;

        hideMessage();
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

    const fieldValue = (id) => (
        document.getElementById(id)?.value.trim() || ""
    );

    boletoButton?.addEventListener("click", async () => {
        const originalText = boletoButton.textContent;
        const cpf = fieldValue("boleto-cpf")
            .replace(/\D/g, "");

        const address = {
            zip_code: fieldValue("boleto-postal-code"),
            street_name: fieldValue("boleto-street"),
            street_number: fieldValue("boleto-number"),
            neighborhood: fieldValue(
                "boleto-neighborhood"
            ),
            city: fieldValue("boleto-city"),
            state: fieldValue("boleto-state")
                .toUpperCase(),
        };

        hideMessage();

        if (cpf.length !== 11) {
            showError(
                "Informe um CPF com 11 números "
                + "para gerar o boleto."
            );
            return;
        }

        const hasMissingAddress = Object.values(
            address
        ).some(value => !value);

        if (hasMissingAddress) {
            showError(
                "Preencha todos os campos de endereço "
                + "para gerar o boleto."
            );
            return;
        }

        if (address.state.length !== 2) {
            showError(
                "Informe o estado com duas letras, como SC."
            );
            return;
        }

        boletoButton.disabled = true;
        boletoButton.textContent = "Gerando boleto...";

        try {
            await processPayment({
                payment_method_id: "boleto",
                payment_type_id: "ticket",
                payer: {
                    email: container.dataset.payerEmail,
                    identification: {
                        type: "CPF",
                        number: cpf,
                    },
                    address,
                },
            });
        } catch (error) {
            showError(error.message);
            boletoButton.disabled = false;
            boletoButton.textContent = originalText;
        }
    });

    const cpfInput = document.getElementById("boleto-cpf");

    cpfInput?.addEventListener("input", () => {
        const digits = cpfInput.value
            .replace(/\D/g, "")
            .slice(0, 11);

        cpfInput.value = digits
            .replace(
                /^(\d{3})(\d)/,
                "$1.$2"
            )
            .replace(
                /^(\d{3})\.(\d{3})(\d)/,
                "$1.$2.$3"
            )
            .replace(
                /\.(\d{3})(\d)/,
                ".$1-$2"
            );
    });

    const postalCodeInput = document.getElementById(
        "boleto-postal-code"
    );

    postalCodeInput?.addEventListener("input", () => {
        const digits = postalCodeInput.value
            .replace(/\D/g, "")
            .slice(0, 8);

        postalCodeInput.value = digits.replace(
            /^(\d{5})(\d)/,
            "$1-$2"
        );
    });

    const stateInput = document.getElementById(
        "boleto-state"
    );

    stateInput?.addEventListener("input", () => {
        stateInput.value = stateInput.value
            .replace(/[^a-zA-Z]/g, "")
            .slice(0, 2)
            .toUpperCase();
    });

    window.addEventListener("pagehide", () => {
        window.cardPaymentBrickController?.unmount();
    });
})();