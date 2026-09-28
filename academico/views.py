from django.shortcuts import render
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
        'alumnos': Alumno.objects.select_related('carrera').all(),
    }
    return render(request, 'academico/alumno_list.html', contexto)