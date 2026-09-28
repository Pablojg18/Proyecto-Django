from django.contrib import admin
from .models import Carrera, Materia, Grupo, Alumno, Calificacion


@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'duracion', 'creditos']
    search_fields = ['codigo', 'nombre']


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'unidades', 'creditos', 'carrera']
    list_filter = ['carrera']
    search_fields = ['codigo', 'nombre']


@admin.register(Grupo)
class GrupoAdmin(admin.ModelAdmin):
    list_display = ['materia', 'periodo', 'turno', 'horario', 'aula', 'cupo', 'num_alumnos']
    list_filter = ['periodo', 'turno', 'materia']
    search_fields = ['periodo', 'horario', 'aula']


class CalificacionInline(admin.TabularInline):
    model = Calificacion
    extra = 0


@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ['matricula', 'nombre', 'semestre', 'estatus', 'carrera']
    list_filter = ['estatus', 'semestre', 'carrera']
    search_fields = ['matricula', 'nombre']
    inlines = [CalificacionInline]


@admin.register(Calificacion)
class CalificacionAdmin(admin.ModelAdmin):
    list_display = ['alumno', 'grupo', 'valor', 'fecha_inscripcion', 'fecha_captura']
    list_filter = ['grupo']
    search_fields = ['alumno__matricula', 'alumno__nombre', 'grupo__periodo']