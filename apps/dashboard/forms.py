from django import forms

from apps.catalog.models import DeviceType, Service


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['device_type', 'name', 'description', 'price_from', 'duration_days', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}


class DeviceTypeForm(forms.ModelForm):
    class Meta:
        model = DeviceType
        fields = ['name']

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if DeviceType.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Такой тип устройства уже есть.')
        return name
