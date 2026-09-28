from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from .forms import CalificacionFormSet
from .models import Carrera, Materia, Grupo, Alumno, Calificacion


def index(request):
    contexto = {
        'carreras': Carrera.objects.all(),
        'materias': Materia.objects.all(),
        'grupos': Grupo.objects.all(),
        'alumnos': Alumno.objects.all(),
        'calificaciones': Calificacion.objects.all(),
    }
    return render(request, 'academico/index.html', contexto)


def alumno_list(request):
    contexto = {
        'alumnos': Alumno.objects.select_related('carrera')
        .prefetch_related('calificaciones').all(),
    }
    return render(request, 'academico/alumno_list.html', contexto)


def alumno_cardex(request, matricula):
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
