(() => {
    const container = document.getElementById(
        "cardPaymentBrick_container"
    );

    if (
        !container
        || typeof MercadoPago === "undefined"
    ) {
        return;
    }

    const message = document.getElementById(
        "payment-message"
    );

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

                onSubmit: (
                    formData,
                    additionalData
                ) => new Promise(
                    (resolve, reject) => {
                        message.hidden = true;

                        const paymentTypeId = (
                            additionalData?.paymentTypeId
                        );

                        if (!paymentTypeId) {
                            const error = new Error(
                                "Não foi possível identificar "
                                + "o tipo do cartão."
                            );

                            showError(error.message);
                            reject(error);
                            return;
                        }

                        fetch(
                            container.dataset.processUrl,
                            {
                                method: "POST",

                                headers: {
                                    "Content-Type":
                                        "application/json",
                                    "X-CSRFToken": csrfToken,
                                },

                                body: JSON.stringify({
                                    ...formData,

                                    payment_type_id:
                                        paymentTypeId,

                                    attempt_id:
                                        container.dataset
                                            .attemptId,
                                }),
                            }
                        )
                            .then(async response => {
                                const data =
                                    await response.json();

                                if (!response.ok) {
                                    throw new Error(
                                        data.error
                                        || "Não foi possível "
                                        + "processar o pagamento."
                                    );
                                }

                                window.location.assign(
                                    data.redirect_url
                                );

                                resolve();
                            })
                            .catch(error => {
                                showError(error.message);
                                reject(error);
                            });
                    }
                ),

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