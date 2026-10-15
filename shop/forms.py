from django import forms


class CartAddForm(forms.Form):
    quantity = forms.IntegerField(
        label="Quantidade",
        min_value=1,
        max_value=10,
        initial=1,
        widget=forms.NumberInput(attrs={"class": "quantity-input", "inputmode": "numeric"}),
    )
    replace = forms.BooleanField(required=False, widget=forms.HiddenInput)
