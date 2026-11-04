document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#checkout-form");
  const addressFields = document.querySelector(
    "#address-fields"
  );
  const deliveryOptions = document.querySelectorAll(
    'input[name="delivery_method"]'
  );
  const postalCodeInput = document.querySelector(
    "#id_postal_code"
  );
  const calculator = document.querySelector(
    ".shipping-calculator"
  );
  const calculateButton = document.querySelector(
    "#calculate-shipping-button"
  );
  const shippingOptions = document.querySelector(
    "#shipping-options"
  );
  const shippingMessage = document.querySelector(
    "#shipping-message"
  );
  const selectedServiceInput = document.querySelector(
    "#shipping-service-id"
  );
  const csrfToken = document.querySelector(
    "[name=csrfmiddlewaretoken]"
  )?.value;

  if (
    !form
    || !addressFields
    || !deliveryOptions.length
  ) {
    return;
  }

  const selectedDeliveryMethod = () => (
    document.querySelector(
      'input[name="delivery_method"]:checked'
    )?.value
  );

  const isShippingSelected = () => (
    !selectedDeliveryMethod()
    || selectedDeliveryMethod() === "shipping"
  );

  const showMessage = (text, isError = false) => {
    if (!shippingMessage) {
      return;
    }

    shippingMessage.textContent = text;
    shippingMessage.classList.toggle(
      "field-error",
      isError
    );
  };

  const clearShippingOptions = () => {
    if (shippingOptions) {
      shippingOptions.replaceChildren();
    }

    if (selectedServiceInput) {
      selectedServiceInput.value = "";
    }
  };

  const updateAddressVisibility = () => {
    const shipping = isShippingSelected();

    addressFields.hidden = !shipping;

    if (!shipping) {
      clearShippingOptions();
    }
  };

  const createShippingOption = (quote) => {
    const label = document.createElement("label");
    label.className = "shipping-option";

    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "shipping_quote";
    radio.value = quote.service_id;

    const content = document.createElement("span");
    content.className = "shipping-option-content";

    const title = document.createElement("strong");
    title.textContent = (
      `${quote.company_name} — ${quote.service_name}`
    );

    const details = document.createElement("span");
    const price = Number(quote.price).toLocaleString(
      "pt-BR",
      {
        style: "currency",
        currency: "BRL",
      }
    );

    details.textContent = (
      `${price} · Prazo estimado: `
      + `${quote.delivery_time} dias úteis`
    );

    content.append(title, details);
    label.append(radio, content);

    radio.addEventListener("change", () => {
      selectedServiceInput.value = quote.service_id;

      showMessage(
        "Opção de entrega selecionada."
      );
    });

    return label;
  };

  calculateButton?.addEventListener(
    "click",
    async () => {
      clearShippingOptions();

      const postalCode = postalCodeInput?.value.trim();

      if (!postalCode) {
        showMessage(
          "Informe o CEP para calcular o frete.",
          true
        );
        postalCodeInput?.focus();
        return;
      }

      calculateButton.disabled = true;
      calculateButton.textContent = "Calculando...";
      showMessage("Consultando opções de entrega...");

      try {
        const response = await fetch(
          calculator.dataset.calculateUrl,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({
              postal_code: postalCode,
            }),
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.error
            || "Não foi possível calcular o frete."
          );
        }

        data.quotes.forEach((quote) => {
          shippingOptions.append(
            createShippingOption(quote)
          );
        });

        showMessage(
          "Escolha uma das opções de entrega."
        );
      } catch (error) {
        showMessage(error.message, true);
      } finally {
        calculateButton.disabled = false;
        calculateButton.textContent = "Calcular frete";
      }
    }
  );

  postalCodeInput?.addEventListener("input", () => {
    clearShippingOptions();

    showMessage(
      "Calcule novamente após informar o CEP."
    );
  });

  form.addEventListener("submit", (event) => {
    if (
      isShippingSelected()
      && !selectedServiceInput?.value
    ) {
      event.preventDefault();

      showMessage(
        "Calcule o frete e escolha uma opção de entrega.",
        true
      );

      calculateButton?.focus();
    }
  });

  deliveryOptions.forEach((option) => {
    option.addEventListener(
      "change",
      updateAddressVisibility
    );
  });

  updateAddressVisibility();
});