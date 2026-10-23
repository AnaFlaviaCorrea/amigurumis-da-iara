(() => {
    const copyButton = document.getElementById(
        "pix-copy-button"
    );
    const pixCode = document.getElementById("pix-code");
    const feedback = document.getElementById(
        "pix-copy-feedback"
    );

    if (!copyButton || !pixCode || !feedback) {
        return;
    }

    const copyWithFallback = () => {
        pixCode.focus();
        pixCode.select();
        pixCode.setSelectionRange(
            0,
            pixCode.value.length
        );

        return document.execCommand("copy");
    };

    copyButton.addEventListener("click", async () => {
        try {
            if (
                navigator.clipboard
                && window.isSecureContext
            ) {
                await navigator.clipboard.writeText(
                    pixCode.value
                );
            } else if (!copyWithFallback()) {
                throw new Error("Falha ao copiar");
            }

            feedback.textContent = "Código Pix copiado!";
            copyButton.textContent = "Código copiado!";
        } catch {
            feedback.textContent = (
                "Não foi possível copiar automaticamente. "
                + "Selecione o código e copie manualmente."
            );
        }
    });
})();