from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render

from ..models import Alumno, Calificacion, Carrera, Grupo, Materia, Periodo
from ..permisos import rol_de

TITULOS_POR_ROL = {
    'ADMINISTRADOR': 'Control escolar',
    'COORDINADOR': 'Coordinación',
    'ESTUDIANTE': 'Portal del estudiante',
}


class IniciarSesion(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['periodo_actual'] = Periodo.actual()
        return contexto


class CerrarSesion(LogoutView):
    http_method_names = ['post', 'options']


def _tarjeta(titulo, descripcion, url, etiqueta, activa=True):
    return {
        'titulo': titulo,
        'descripcion': descripcion,
        'url': url,
        'etiqueta': etiqueta,
        'activa': activa,
    }


@login_required
def index(request):
    """Portada: cada tarjeta es una operación disponible para el rol."""
    rol = rol_de(request.user)
    periodo = Periodo.actual()
    tarjetas = []

    if rol in ('ADMINISTRADOR', 'COORDINADOR'):
        tarjetas = [
            _tarjeta(
                'Usuarios',
                'Altas, roles, contraseñas y bajas de acceso al sistema.',
                'usuario_list', 'Administrar'),
            _tarjeta(
                'Alumnos',
                'Registra alumnos nuevos y edita los existentes.',
                'alumno_list', 'Administrar'),
            _tarjeta(
                'Inscripción',
                'Registra y da de baja materias por alumno.',
                'inscripcion_alumnos', 'Administrar'),
            _tarjeta(
                'Periodos',
                'Abre o cierra periodos y elige cuál es el vigente.',
                'periodo_list', 'Administrar'),
            _tarjeta(
                'Grupos',
                'Horarios y cupos que se ofrecen en cada periodo.',
                'grupo_list', 'Administrar'),
            _tarjeta(
                'Materias',
                'Catálogo de materias de cada carrera.',
                'materia_list', 'Administrar'),
            _tarjeta(
                'Carreras',
                'Planes de estudio y sus créditos.',
                'carrera_list', 'Administrar'),
        ]
    elif rol == 'ESTUDIANTE':
        alumno = getattr(request.user.perfil, 'alumno', None)
        tarjetas = [
            _tarjeta(
                'Inscripción',
                'Elige las materias del periodo vigente.',
                'mi_inscripcion', 'Inscribirme'),
            _tarjeta(
                'Carga académica',
                'Materias en curso, créditos y promedio.',
                'mi_carga_academica', 'Consultar'),
            _tarjeta(
                'Mi cardex',
                'Historial de materias y calificaciones.',
                'mi_cardex', 'Ver'),
        ]
        if alumno is None:
            tarjetas = []

    return render(request, 'academico/index.html', {
        'titulo': TITULOS_POR_ROL.get(rol, 'Sistema escolar'),
        'tarjetas': tarjetas,
        'periodo_actual': periodo,
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