(() => {
    const container = document.getElementById("paymentBrick_container");
    if (!container || typeof MercadoPago === "undefined") return;

    const message = document.getElementById("payment-message");
    const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value
        || document.cookie.split("; ").find(row => row.startsWith("csrftoken="))?.split("=")[1];

    const showError = (text) => {
        message.textContent = text;
        message.hidden = false;
    };

    const mercadoPago = new MercadoPago(container.dataset.publicKey, {locale: "pt-BR"});
    const bricksBuilder = mercadoPago.bricks();

    const renderPaymentBrick = async () => {
        const settings = {
            initialization: {
                amount: Number(container.dataset.amount.replace(",", ".")),
                payer: {email: container.dataset.payerEmail},
            },
            customization: {
                paymentMethods: {
                    bankTransfer: "all",
                    creditCard: "all",
                    debitCard: "all",
                    ticket: "all",
                },
                visual: {style: {theme: "default"}},
            },
            callbacks: {
                onReady: () => {},
                onSubmit: ({formData}) => new Promise((resolve, reject) => {
                    message.hidden = true;
                    fetch(container.dataset.processUrl, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": csrfToken,
                        },
                        body: JSON.stringify({...formData, attempt_id: container.dataset.attemptId}),
                    })
                        .then(async response => {
                            const data = await response.json();
                            if (!response.ok) throw new Error(data.error || "Não foi possível processar o pagamento.");
                            window.location.assign(data.redirect_url);
                            resolve();
                        })
                        .catch(error => {
                            showError(error.message);
                            reject(error);
                        });
                }),
                onError: () => showError("O formulário de pagamento encontrou um erro. Atualize a página e tente novamente."),
            },
        };
        window.paymentBrickController = await bricksBuilder.create("payment", "paymentBrick_container", settings);
    };

    renderPaymentBrick().catch(() => showError("Não foi possível carregar as formas de pagamento."));
})();
