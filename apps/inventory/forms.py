from django import forms

from .models import Part


class PartForm(forms.ModelForm):
    class Meta:
        model = Part
        fields = ['sku', 'name', 'device_types', 'price', 'quantity', 'min_quantity']
        widgets = {'device_types': forms.CheckboxSelectMultiple}
        help_texts = {
            'device_types': 'Пусто — универсальная запчасть.',
            'quantity': 'Начальный остаток. Дальше остаток меняется приходом и списанием.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Остаток существующей запчасти меняется только через движения склада.
            del self.fields['quantity']

    def clean_sku(self):
        return self.cleaned_data['sku'].strip().upper()


class ReceiveForm(forms.Form):
    quantity = forms.IntegerField(label='Пришло, шт.', min_value=1, max_value=100_000)
    note = forms.CharField(label='Примечание', max_length=200, required=False)


class AdjustForm(forms.Form):
    quantity = forms.IntegerField(label='Фактический остаток, шт.', min_value=0, max_value=100_000)
    note = forms.CharField(label='Причина', max_length=200)
