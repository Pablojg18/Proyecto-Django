"""Consulta de la carga académica de un alumno."""

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Alumno
from ..permisos import perfil_de, requiere_rol

ROLES_CONTROL = ('ADMINISTRADOR', 'COORDINADOR')
ROLES_ESTUDIANTE = ('ESTUDIANTE',)


def contexto_carga(alumno):
    historial = (alumno.calificaciones
                 .select_related('grupo', 'grupo__materia')
                 .order_by('grupo__periodo', 'grupo__materia__codigo'))
    return {
        'alumno': alumno,
        'carga_actual': list(alumno.carga_academica()),
        'historial': historial,
        'materias_cursadas': alumno.materias_cursadas,
        'creditos_en_curso': alumno.creditos_en_curso,
        'creditos_acumulados': alumno.creditos_acumulados,
        'promedio_general': alumno.promedio_general,
        'avance_carrera': alumno.avance_carrera,
        'periodo_actual': settings.PERIODO_ACTUAL,
    }


@requiere_rol(*ROLES_CONTROL)
def carga_de_alumno(request, matricula):
    """Carga académica de cualquier alumno (coordinador o administrador)."""
    alumno = get_object_or_404(
        Alumno.objects.select_related('carrera'), matricula=matricula)
    return render(request, 'academico/carga_academica.html',
                  contexto_carga(alumno))


@requiere_rol(*ROLES_ESTUDIANTE)
def mi_carga_academica(request):
    """Carga académica del estudiante que inició sesión."""
    perfil = perfil_de(request.user)
    if perfil is None or perfil.alumno_id is None:
        messages.error(request, 'Tu usuario no tiene un alumno asociado.')
        return redirect('index')
    alumno = get_object_or_404(
        Alumno.objects.select_related('carrera'), pk=perfil.alumno_id)
    return render(request, 'academico/carga_academica.html',
                  contexto_carga(alumno))