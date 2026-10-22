from django import forms

from .models import Order


class CartAddForm(forms.Form):
    quantity = forms.IntegerField(
        label="Quantidade",
        min_value=1,
        max_value=10,
        initial=1,
        widget=forms.NumberInput(attrs={"class": "quantity-input", "inputmode": "numeric"}),
    )
    replace = forms.BooleanField(required=False, widget=forms.HiddenInput)


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = (
            "full_name",
            "email",
            "phone",
            "delivery_method",
            "postal_code",
            "street",
            "number",
            "complement",
            "neighborhood",
            "city",
            "state",
            "customer_notes",
        )
        widgets = {
            "delivery_method": forms.RadioSelect,
            "customer_notes": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Conte algo importante sobre o pedido."}
            ),
            "postal_code": forms.TextInput(attrs={"placeholder": "00000-000", "inputmode": "numeric"}),
            "phone": forms.TextInput(attrs={"placeholder": "(48) 99999-9999", "inputmode": "tel"}),
            "state": forms.TextInput(attrs={"maxlength": 2, "placeholder": "SC"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != "delivery_method":
                field.widget.attrs["class"] = "checkout-input"
        self.fields["full_name"].widget.attrs["autocomplete"] = "name"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["phone"].widget.attrs["autocomplete"] = "tel"
        self.fields["postal_code"].widget.attrs["autocomplete"] = "postal-code"

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("delivery_method") == Order.DeliveryMethod.SHIPPING:
            required_address_fields = {
                "postal_code": "CEP",
                "street": "Rua",
                "number": "Número",
                "neighborhood": "Bairro",
                "city": "Cidade",
                "state": "Estado",
            }
            for field_name, label in required_address_fields.items():
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, f"Informe {label.lower()} para receber o pedido.")

        state = cleaned_data.get("state", "")
        if state:
            cleaned_data["state"] = state.upper()
        return cleaned_data
