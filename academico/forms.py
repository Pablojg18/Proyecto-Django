from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.conf import settings

from .models import (Alumno, Calificacion, Carrera, Grupo, Materia, Perfil,
                     Periodo)
from .permisos import rol_de

ROLES_PERSONAL = (('ADMINISTRADOR', 'Administrador'),
                  ('COORDINADOR', 'Coordinador'))
ROLES_FUNCIONAL = (('COORDINADOR', 'Coordinador'),
                   ('ESTUDIANTE', 'Estudiante'))


def validar_password_inicial(password):
    minimo = settings.LONGITUD_MINIMA_PASSWORD_INICIAL
    if len(password) < minimo:
        raise ValidationError(
            f'La contraseña debe tener al menos {minimo} caracteres.')
    return password


def roles_que_pueden_asignar(usuario):
    """El coordinador no puede crear administradores."""
    if rol_de(usuario) == 'ADMINISTRADOR':
        return ROLES_PERSONAL + ROLES_FUNCIONAL
    return ROLES_FUNCIONAL


class AlumnoForm(forms.ModelForm):
    """Alta y edición de alumnos; al crear uno se genera su usuario."""

    password_inicial = forms.CharField(
        required=False,
        label='Contraseña inicial',
        widget=forms.PasswordInput(render_value=False),
        help_text=(
            'Con ella el alumno inicia sesión para inscribirse y consultar su '
            'carga académica. Solo se usa al dar de alta; después se cambia '
            'desde Usuarios.'
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
        if password:
            return validar_password_inicial(password)
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
            'codigo': forms.TextInput(attrs={'placeholder': 'MAT103'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre de la materia'}),
            'unidades': forms.NumberInput(attrs={'min': 1}),
            'creditos': forms.NumberInput(attrs={'min': 1}),
        }


class PeriodoForm(forms.ModelForm):
    class Meta:
        model = Periodo
        fields = ['nombre', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': '2026-2'}),
        }
        help_texts = {
            'nombre': 'Escribe el periodo tal como lo verá el alumno, por '
                      'ejemplo 2026-1, 2026-2 o AGO-DIC.',
            'activo': 'Solo puede haber un periodo activo. Las inscripciones '
                      'se hacen únicamente en el periodo activo.',
        }


class GrupoForm(forms.ModelForm):
    class Meta:
        model = Grupo
        fields = ['materia', 'periodo', 'turno', 'horario', 'aula',
                  'cupo', 'num_alumnos']
        widgets = {
            'horario': forms.TextInput(attrs={'placeholder': 'L-V 08:00-09:30'}),
            'cupo': forms.NumberInput(attrs={'min': 1}),
            'num_alumnos': forms.NumberInput(attrs={'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['materia'].queryset = (
            Materia.objects.select_related('carrera').order_by('carrera', 'codigo')
        )
        self.fields['periodo'].queryset = Periodo.objects.order_by('-nombre')
        self.fields['periodo'].help_text = (
            'Los grupos se ofrecen para inscripción solo si pertenecen al '
            'periodo activo.')
        self.fields['periodo'].empty_label = 'Elige un periodo'


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


# --- Gestión de usuarios ----------------------------------------------------

class AlumnosSinUsuario(forms.Form):
    """Vincula un alumno que ya existía sin acceso al sistema."""

    alumno = forms.ModelChoiceField(
        queryset=Alumno.objects.select_related('carrera').order_by('matricula'),
        label='Alumno existente',
        help_text='Solo aparecen los alumnos que todavía no tienen usuario.',
    )
    password_inicial = forms.CharField(
        label='Contraseña inicial',
        widget=forms.PasswordInput(render_value=False),
        help_text='Con ella el alumno podrá iniciar sesión.',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['alumno'].queryset = alumnos_sin_usuario()

    def clean_password_inicial(self):
        return validar_password_inicial(
            self.cleaned_data.get('password_inicial') or '')

    def save(self):
        alumno = self.cleaned_data['alumno']
        usuario = User.objects.create_user(
            username=alumno.matricula,
            password=self.cleaned_data['password_inicial'],
            first_name=alumno.nombre,
        )
        Perfil.objects.create(usuario=usuario, rol='ESTUDIANTE', alumno=alumno)
        return usuario


class UsuarioPersonalForm(forms.Form):
    """Alta de coordinador o administrador."""

    username = forms.CharField(
        label='Usuario',
        help_text='Nombre con el que initiate sesión. Para alumnos se usa la '
                  'matrícula.',
    )
    nombre = forms.CharField(label='Nombre completo')
    rol = forms.ChoiceField(label='Rol')
    password_inicial = forms.CharField(
        label='Contraseña inicial',
        widget=forms.PasswordInput(render_value=False),
    )

    def __init__(self, *args, roles_permitidos=ROLES_PERSONAL, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rol'].choices = roles_permitidos

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if not username.isalnum():
            raise ValidationError(
                'El usuario solo puede llevar letras y números, sin espacios.')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('Ese nombre de usuario ya existe.')
        return username

    def clean_password_inicial(self):
        return validar_password_inicial(
            self.cleaned_data.get('password_inicial') or '')

    def save(self):
        datos = self.cleaned_data
        usuario = User.objects.create_user(
            username=datos['username'],
            password=datos['password_inicial'],
            first_name=datos['nombre'],
        )
        Perfil.objects.create(usuario=usuario, rol=datos['rol'])
        return usuario


class UsuarioEdicionForm(forms.ModelForm):
    """Cambia nombre, rol y estado de un usuario."""

    rol = forms.ChoiceField(label='Rol')
    alumno = forms.ModelChoiceField(
        queryset=Alumno.objects.select_related('carrera').order_by('matricula'),
        required=False,
        label='Alumno asociado',
        help_text='Solo para usuarios con rol Estudiante.',
    )

    class Meta:
        model = User
        fields = ['first_name', 'is_active']

    def __init__(self, *args, roles_permitidos=ROLES_PERSONAL, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rol'].choices = roles_permitidos
        self.fields['first_name'].label = 'Nombre completo'
        self.fields['is_active'].label = 'Puede iniciar sesión'
        perfil = getattr(self.instance, 'perfil', None)
        if perfil is None:
            self.fields['rol'].initial = 'COORDINADOR'
        else:
            self.fields['rol'].initial = perfil.rol
            self.fields['alumno'].initial = perfil.alumno_id

    def clean_alumno(self):
        alumno = self.cleaned_data.get('alumno')
        if alumno is not None and Perfil.objects.filter(
                alumno=alumno).exclude(usuario=self.instance).exists():
            raise ValidationError('Ese alumno ya está asociado a otro usuario.')
        return alumno

    def save(self, commit=True):
        usuario = super().save(commit=commit)
        perfil, _ = Perfil.objects.get_or_create(usuario=usuario)
        perfil.rol = self.cleaned_data['rol']
        perfil.alumno = (self.cleaned_data['alumno']
                         if perfil.rol == 'ESTUDIANTE' else None)
        perfil.save()
        return usuario


class PasswordForm(forms.Form):
    """Asigna o cambia la contraseña de un usuario."""

    password = forms.CharField(
        label='Nueva contraseña',
        widget=forms.PasswordInput(render_value=False),
    )
    repetir = forms.CharField(
        label='Repetir contraseña',
        widget=forms.PasswordInput(render_value=False),
        help_text='El usuario deberá cambiarla al entrar.',
    )

    def clean(self):
        datos = super().clean()
        if datos.get('password') and datos['password'] != datos.get('repetir'):
            raise ValidationError('Las contraseñas no coinciden.')
        if datos.get('password'):
            validar_password_inicial(datos['password'])
        return datos

    def aplicar(self, usuario):
        usuario.set_password(self.cleaned_data['password'])
        usuario.save(update_fields=['password'])


def alumnos_sin_usuario():
    return (Alumno.objects
            .filter(perfil_de_alumno__isnull=True)
            .select_related('carrera')
            .order_by('matricula'))