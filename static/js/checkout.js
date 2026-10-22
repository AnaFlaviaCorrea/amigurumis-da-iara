document.addEventListener("DOMContentLoaded", () => {
  const addressFields = document.querySelector("#address-fields");
  const deliveryOptions = document.querySelectorAll('input[name="delivery_method"]');

  if (!addressFields || !deliveryOptions.length) return;

  const updateAddressVisibility = () => {
    const selected = document.querySelector('input[name="delivery_method"]:checked');
    const isShipping = !selected || selected.value === "shipping";
    addressFields.hidden = !isShipping;
  };

  deliveryOptions.forEach((option) => option.addEventListener("change", updateAddressVisibility));
  updateAddressVisibility();
});
