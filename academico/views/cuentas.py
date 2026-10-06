from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render

from ..models import Alumno, Calificacion, Carrera, Grupo, Materia, Periodo
from ..permisos import perfil_de, rol_de


def _alumno_de_la_sesion(request):
    """Alumno del usuario conectado, o None si no tiene uno."""
    perfil = perfil_de(request.user)
    return perfil.alumno if perfil else None

TITULOS_POR_ROL = {
    'ADMINISTRADOR': 'Control escolar',
    'COORDINADOR': 'Coordinación',
    'ESTUDIANTE': 'Portal del estudiante',
}

# Tarjetas de la portada: (título, descripción, ruta, etiqueta del botón).
TARJETAS_CONTROL = [
    ('Usuarios', 'Altas, roles, contraseñas y bajas de acceso al sistema.',
     'usuario_list', 'Administrar'),
    ('Alumnos', 'Registra alumnos nuevos y edita los existentes.',
     'alumno_list', 'Administrar'),
    ('Inscripción', 'Registra y da de baja materias por alumno.',
     'inscripcion_alumnos', 'Administrar'),
    ('Periodos', 'Abre o cierra periodos y elige cuál es el vigente.',
     'periodo_list', 'Administrar'),
    ('Grupos', 'Horarios y cupos que se ofrecen en cada periodo.',
     'grupo_list', 'Administrar'),
    ('Materias', 'Catálogo de materias de cada carrera.',
     'materia_list', 'Administrar'),
    ('Carreras', 'Planes de estudio y sus créditos.',
     'carrera_list', 'Administrar'),
]

TARJETAS_ESTUDIANTE = [
    ('Inscripción', 'Elige las materias del periodo vigente.',
     'mi_inscripcion', 'Inscribirme'),
    ('Carga académica', 'Materias en curso, créditos y promedio.',
     'mi_carga_academica', 'Consultar'),
    ('Mi cardex', 'Historial de materias y calificaciones.',
     'mi_cardex', 'Ver'),
]


class IniciarSesion(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['periodo_actual'] = Periodo.actual()
        return contexto


class CerrarSesion(LogoutView):
    http_method_names = ['post', 'options']


def _tarjetas(rol, alumno):
    """Tarjetas disponibles para el rol, ya en el formato de la plantilla."""
    if rol in ('ADMINISTRADOR', 'COORDINADOR'):
        datos = TARJETAS_CONTROL
    elif rol == 'ESTUDIANTE' and alumno is not None:
        datos = TARJETAS_ESTUDIANTE
    else:
        return []
    return [
        {'titulo': titulo, 'descripcion': descripcion, 'url': url,
         'etiqueta': etiqueta}
        for titulo, descripcion, url, etiqueta in datos
    ]


@login_required
def index(request):
    """Portada: cada tarjeta es una operación disponible para el rol."""
    rol = rol_de(request.user)
    return render(request, 'academico/index.html', {
        'titulo': TITULOS_POR_ROL.get(rol, 'Sistema escolar'),
        'tarjetas': _tarjetas(rol, _alumno_de_la_sesion(request)),
        'periodo_actual': Periodo.actual(),
        'resumen': _resumen(rol),
    })


def _resumen(rol):
    """Cifras rápidas del periodo vigente."""
    periodo = Periodo.actual()
    if periodo is None or rol == 'ESTUDIANTE':
        return {}
    return {
        'Alumnos': Alumno.objects.count(),
        'Carreras': Carrera.objects.count(),
        'Materias': Materia.objects.count(),
        'Grupos del periodo': Grupo.objects.filter(periodo=periodo).count(),
        'Inscripciones del periodo': Calificacion.objects.filter(
            grupo__periodo=periodo).count(),
        'Usuarios': User.objects.count(),
    }