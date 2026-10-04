from django.conf import settings
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..models import Alumno, Calificacion, Carrera, Grupo, Materia
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
        contexto['periodo_actual'] = settings.PERIODO_ACTUAL
        return contexto


class CerrarSesion(LogoutView):
    http_method_names = ['post', 'options']


@login_required
def index(request):
    """Portada: dashboard con las operaciones permitidas al rol del usuario."""
    rol = rol_de(request.user)
    resumen = {}
    if rol == 'ADMINISTRADOR':
        resumen = {
            'Alumnos': Alumno.objects.count(),
            'Carreras': Carrera.objects.count(),
            'Materias': Materia.objects.count(),
        }
    elif rol == 'COORDINADOR':
        resumen = {
            'Grupos del periodo': Grupo.objects.filter(
                periodo=settings.PERIODO_ACTUAL).count(),
            'Alumnos': Alumno.objects.count(),
            'Inscripciones del periodo': Calificacion.objects.filter(
                grupo__periodo=settings.PERIODO_ACTUAL).count(),
        }
    elif rol == 'ESTUDIANTE':
        alumno = getattr(request.user.perfil, 'alumno', None)
        if alumno is not None:
            resumen = {
                'Materias en curso': alumno.carga_academica().count(),
                'Materias cursadas': alumno.materias_cursadas,
                'Créditos acumulados': alumno.creditos_acumulados,
            }

    contexto = {
        'titulo': TITULOS_POR_ROL.get(rol, 'Sistema escolar'),
        'resumen': resumen,
        'periodo_actual': settings.PERIODO_ACTUAL,
    }
    return render(request, 'academico/index.html', contexto)