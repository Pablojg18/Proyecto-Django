"""Cardex: editable para administración/coordinación, de solo lectura para el
estudiante."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..forms import CalificacionFormSet
from ..models import Alumno, Calificacion
from ..permisos import requiere_rol

ROLES_COORDINACION = ('ADMINISTRADOR', 'COORDINADOR')


def _contexto_cardex(alumno, formset=None, solo_lectura=False):
    return {
        'alumno': alumno,
        'formset': formset,
        'solo_lectura': solo_lectura,
        'calificaciones': alumno.calificaciones.select_related(
            'grupo', 'grupo__materia', 'grupo__periodo'
        ).order_by('grupo__periodo__nombre', 'grupo__materia__codigo'),
        'materias_cursadas': alumno.materias_cursadas,
        'creditos_acumulados': alumno.creditos_acumulados,
        'promedio_general': alumno.promedio_general,
    }


@requiere_rol(*ROLES_COORDINACION)
def alumno_cardex(request, matricula):
    """Muestra y guarda las calificaciones finales de un alumno."""
    alumno = get_object_or_404(
        Alumno.objects.select_related('carrera'), matricula=matricula
    )

    formset = CalificacionFormSet(
        request.POST if request.method == 'POST' else None,
        queryset=alumno.calificaciones.select_related(
            'grupo', 'grupo__materia', 'grupo__periodo'),
    )
    if request.method == 'POST' and formset.is_valid():
        formset.save()
        hoy = timezone.localdate()
        Calificacion.objects.filter(
            alumno=alumno, valor__isnull=False).update(fecha_captura=hoy)
        Calificacion.objects.filter(
            alumno=alumno, valor__isnull=True).update(fecha_captura=None)
        messages.success(
            request, f'Se guardó el cardex de {alumno.matricula}.')
        return redirect('alumno_cardex', matricula=alumno.matricula)

    return render(request, 'academico/alumno_cardex.html',
                  _contexto_cardex(alumno, formset))


@requiere_rol('ESTUDIANTE')
def mi_cardex(request):
    """El estudiante solo consulta su propio historial, sin editarlo."""
    alumno = getattr(request.user.perfil, 'alumno', None)
    if alumno is None:
        messages.error(
            request, 'Tu usuario no está asociado a un alumno registrado.')
        return redirect('index')
    return render(request, 'academico/alumno_cardex.html',
                  _contexto_cardex(alumno, solo_lectura=True))