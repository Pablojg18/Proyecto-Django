"""Captura de calificaciones finales (funcionalidad de la tarea anterior)."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..forms import CalificacionFormSet
from ..models import Alumno, Calificacion
from ..permisos import requiere_rol

ROLES_COORDINADOR = ('COORDINADOR',)


@requiere_rol(*ROLES_COORDINADOR)
def alumno_cardex(request, matricula):
    """Muestra y guarda las calificaciones finales de un alumno."""
    alumno = get_object_or_404(
        Alumno.objects.select_related('carrera'), matricula=matricula
    )
    calificaciones = alumno.calificaciones.select_related(
        'grupo', 'grupo__materia'
    ).order_by('grupo__periodo', 'grupo__materia__codigo')

    formset = CalificacionFormSet(
        request.POST if request.method == 'POST' else None,
        queryset=calificaciones,
    )
    if request.method == 'POST' and formset.is_valid():
        formset.save()
        hoy = timezone.localdate()
        Calificacion.objects.filter(alumno=alumno, valor__isnull=False).update(
            fecha_captura=hoy
        )
        Calificacion.objects.filter(alumno=alumno, valor__isnull=True).update(
            fecha_captura=None
        )
        messages.success(
            request, f'Se guardó el cardex de {alumno.matricula}.'
        )
        return redirect('alumno_cardex', matricula=alumno.matricula)

    contexto = {
        'alumno': alumno,
        'formset': formset,
    }
    return render(request, 'academico/alumno_cardex.html', contexto)