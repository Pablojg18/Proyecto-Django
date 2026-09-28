from django import forms
from .models import Calificacion


class CalificacionForm(forms.ModelForm):
    class Meta:
        model = Calificacion
        fields = ['valor']
        widgets = {
            'valor': forms.NumberInput(
                attrs={'step': '0.1', 'min': '0', 'max': '10',
                       'class': 'campo-calificacion'}
            ),
        }


CalificacionFormSet = forms.modelformset_factory(
    Calificacion,
    form=CalificacionForm,
    extra=0,
    can_delete=False,
)
