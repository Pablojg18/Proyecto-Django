from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.conf import settings

from .models import Alumno, Calificacion, Carrera, Grupo, Materia, Perfil


class AlumnoForm(forms.ModelForm):
    """Alta y edición de alumnos; al crear uno se genera su usuario."""

    password_inicial = forms.CharField(
        required=False,
        label='Contraseña inicial',
        widget=forms.PasswordInput(render_value=False),
        help_text=(
            'Se usa solo al dar de alta al alumno: con ella podrá iniciar '
            'sesión para inscribirse y consultar su carga académica.'
        ),
    )

    class Meta:
        model = Alumno
        fields = ['matricula', 'nombre', 'carrera', 'semestre',
                  'especialidad', 'estatus']
        widgets = {
            'matricula': forms.TextInput(attrs={'placeholder': '20260001'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre completo'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ojo: la matrícula es la clave primaria del alumno, así que un alumno
        # sin guardar tiene la.pk vacía (''), no None.
        self.es_nuevo = not self.instance.pk
        self.fields['password_inicial'].required = self.es_nuevo

    def clean_password_inicial(self):
        password = self.cleaned_data.get('password_inicial')
        if not password:
            return password
        if len(password) < settings.LONGITUD_MINIMA_PASSWORD_INICIAL:
            raise ValidationError(
                f'La contraseña debe tener al menos '
                f'{settings.LONGITUD_MINIMA_PASSWORD_INICIAL} caracteres.'
            )
        return password

    def clean_matricula(self):
        matricula = self.cleaned_data['matricula'].strip()
        if self.es_nuevo and User.objects.filter(username__iexact=matricula).exists():
            raise ValidationError('Ya existe un usuario con esta matrícula.')
        return matricula

    def save(self, commit=True):
        alumno = super().save(commit=commit)
        if commit and alumno.pk and self.es_nuevo:
            usuario = User.objects.create_user(
                username=alumno.matricula,
                password=self.cleaned_data['password_inicial'],
                first_name=alumno.nombre,
            )
            Perfil.objects.create(usuario=usuario, rol='ESTUDIANTE',
                                  alumno=alumno)
        return alumno


class CarreraForm(forms.ModelForm):
    class Meta:
        model = Carrera
        fields = ['codigo', 'nombre', 'duracion', 'creditos']
        widgets = {
            'codigo': forms.TextInput(attrs={'placeholder': 'ISC'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Ingeniería en Sistemas'}),
            'duracion': forms.NumberInput(attrs={'min': 1, 'max': 20}),
            'creditos': forms.NumberInput(attrs={'min': 1}),
        }


class MateriaForm(forms.ModelForm):
    class Meta:
        model = Materia
        fields = ['codigo', 'nombre', 'carrera', 'unidades', 'creditos']
        widgets = {
            'codigo': forms.TextInput(attrs={'placeholder': 'MAT101'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre de la materia'}),
            'unidades': forms.NumberInput(attrs={'min': 1}),
            'creditos': forms.NumberInput(attrs={'min': 1}),
        }


class GrupoForm(forms.ModelForm):
    class Meta:
        model = Grupo
        fields = ['materia', 'periodo', 'turno', 'horario', 'aula',
                  'cupo', 'num_alumnos']
        widgets = {
            'periodo': forms.TextInput(attrs={'placeholder': '2026-1'}),
            'horario': forms.TextInput(attrs={'placeholder': 'L-V 08:00-09:30'}),
            'cupo': forms.NumberInput(attrs={'min': 1}),
            'num_alumnos': forms.NumberInput(attrs={'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['materia'].queryset = (
            Materia.objects.select_related('carrera').order_by('carrera', 'codigo')
        )


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


def grupos_inscribibles(alumno, periodo):
    """Grupos del periodo con el motivo por el que el alumno no puede entrar.

    Devuelve una lista de diccionarios: ``grupo``, ``disponible`` y ``motivo``.
    """
    grupos = (Grupo.objects
              .filter(periodo=periodo, materia__carrera=alumno.carrera)
              .select_related('materia')
              .order_by('materia__codigo', 'turno', 'horario'))

    opciones = []
    for grupo in grupos:
        if alumno.ha_cursado(grupo.materia):
            disponible, motivo = False, 'Materia ya cursada'
        elif grupo.esta_lleno:
            disponible, motivo = False, 'Grupo sin cupo'
        else:
            disponible, motivo = True, ''
        opciones.append({
            'grupo': grupo,
            'disponible': disponible,
            'motivo': motivo,
        })
    return opciones


class GruposChoiceField(forms.ModelMultipleChoiceField):
    """Muestra en la casilla toda la información que el alumno necesita."""

    widget = forms.CheckboxSelectMultiple

    def label_from_instance(self, grupo):
        return (f'{grupo.materia.codigo} – {grupo.materia.nombre} · '
                f'{grupo.get_turno_display()} {grupo.horario} · '
                f'Aula {grupo.aula or "—"} · '
                f'{grupo.lugares_disponibles} de {grupo.cupo} lugares')


class InscripcionForm(forms.Form):
    """Selección múltiple de grupos para inscribir a un alumno."""

    grupos = GruposChoiceField(
        queryset=Grupo.objects.none(),
        label='Materias a cursar',
    )

    def __init__(self, *args, opciones=None, **kwargs):
        super().__init__(*args, **kwargs)
        disponibles = [o['grupo'] for o in (opciones or []) if o['disponible']]
        self.fields['grupos'].queryset = Grupo.objects.filter(
            pk__in=[g.pk for g in disponibles]
        ).order_by('materia__codigo', 'turno', 'horario')


class FiltroAlumnosForm(forms.Form):
    """Búsqueda de alumnos por matrícula, nombre o carrera."""

    q = forms.CharField(
        required=False,
        label='Buscar',
        widget=forms.TextInput(attrs={'placeholder': 'Matrícula, nombre o carrera'}),
    )
    carrera = forms.ModelChoiceField(
        required=False,
        queryset=Carrera.objects.all(),
        label='Carrera',
        empty_label='Todas las carreras',
    )