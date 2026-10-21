from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.catalog.models import Service
from apps.inventory.models import Part

from .models import RepairRequest, Status


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """ImageField, принимающий несколько файлов. Каждый проверяется Pillow."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleImageInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        if len(files) > settings.MAX_PHOTOS_PER_REQUEST:
            raise ValidationError(f'Можно прикрепить не больше {settings.MAX_PHOTOS_PER_REQUEST} фото.')
        cleaned = []
        for f in files:
            if f.size > settings.MAX_PHOTO_SIZE:
                raise ValidationError(f'Файл «{f.name}» больше {settings.MAX_PHOTO_SIZE // 1024 // 1024} МБ.')
            cleaned.append(super().clean(f, initial))
        return cleaned


class RepairRequestForm(forms.ModelForm):
    photos = MultipleImageField(
        label='Фото устройства', required=False,
        help_text=f'JPEG, PNG или WebP, до {settings.MAX_PHOTOS_PER_REQUEST} файлов по 5 МБ.',
    )

    class Meta:
        model = RepairRequest
        fields = ['device_type', 'device_model', 'serial_number', 'service', 'problem']
        widgets = {
            'problem': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Что случилось, когда появилась проблема…'}),
            'device_model': forms.TextInput(attrs={'placeholder': 'Например, iPhone 13 или Lenovo IdeaPad 5'}),
        }
        help_texts = {'service': 'Если не знаете, что сломалось, оставьте пустым — мастер проведёт диагностику.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service'].queryset = Service.objects.filter(is_active=True).select_related('device_type')
        self.fields['service'].required = False

    def clean_problem(self):
        problem = self.cleaned_data['problem'].strip()
        if len(problem) < 10:
            raise ValidationError('Опишите неисправность подробнее (не меньше 10 символов).')
        if len(problem) > 2000:
            raise ValidationError('Описание не должно быть длиннее 2000 символов.')
        return problem

    def clean(self):
        cleaned = super().clean()
        service, device_type = cleaned.get('service'), cleaned.get('device_type')
        if service and device_type and service.device_type_id != device_type.pk:
            self.add_error('service', 'Эта услуга относится к другому типу устройства.')
        return cleaned


class StatusForm(forms.Form):
    status = forms.ChoiceField(label='Новый статус', choices=Status.choices)

    def __init__(self, *args, request_obj=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if request_obj is None or user is None:
            return
        if user.is_admin_role:
            self.fields['status'].initial = request_obj.status
        else:
            allowed = request_obj.allowed_statuses()
            self.fields['status'].choices = [(s.value, s.label) for s in allowed]


class CommentForm(forms.Form):
    text = forms.CharField(
        label='Комментарий', max_length=2000, widget=forms.Textarea(attrs={'rows': 3}),
    )
    is_internal = forms.BooleanField(label='Только для сотрудников', required=False)

    def clean_text(self):
        text = self.cleaned_data['text'].strip()
        if not text:
            raise ValidationError('Комментарий не может быть пустым.')
        return text


class PartUsageForm(forms.Form):
    part = forms.ModelChoiceField(label='Запчасть', queryset=Part.objects.none(), empty_label='— выберите запчасть —')
    quantity = forms.IntegerField(label='Кол-во', min_value=1, max_value=999, initial=1)

    def __init__(self, *args, device_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Part.objects.filter(quantity__gt=0)
        if device_type is not None:
            # Подходящие к устройству — первыми, универсальные (без привязки) тоже показываем.
            qs = qs.filter(device_types=device_type) | qs.filter(device_types=None)
        self.fields['part'].queryset = qs.distinct().order_by('name')
        self.fields['part'].label_from_instance = lambda p: f'{p.name} — {p.price} ₽ (ост. {p.quantity})'


class LaborCostForm(forms.Form):
    labor_cost = forms.DecimalField(label='Стоимость работ, ₽', min_value=0, max_value=1_000_000, decimal_places=2)


class AssignForm(forms.Form):
    master = forms.ModelChoiceField(
        label='Мастер', required=False, empty_label='— не назначен —',
        queryset=User.objects.filter(role=User.Role.MASTER, is_active=True),
    )
