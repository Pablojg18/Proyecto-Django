from django.contrib import admin
from .models import (Alumno, Calificacion, CalificacionUnidad, Carrera,
                     Grupo, Materia, Perfil)


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
    list_display = ['materia', 'periodo', 'hora_inicio', 'hora_fin', 'aula',
                    'cupo', 'num_alumnos']
    list_filter = ['periodo', 'hora_inicio', 'materia']
    search_fields = ['materia__codigo', 'materia__nombre', 'aula']


class CalificacionUnidadInline(admin.TabularInline):
    model = CalificacionUnidad
    extra = 0


class CalificacionInline(admin.TabularInline):
    model = Calificacion
    extra = 0
    show_change_link = True


@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ['matricula', 'nombre', 'semestre', 'estatus', 'carrera']
    list_filter = ['estatus', 'semestre', 'carrera']
    search_fields = ['matricula', 'nombre']
    inlines = [CalificacionInline]


@admin.register(Calificacion)
class CalificacionAdmin(admin.ModelAdmin):
    list_display = ['alumno', 'grupo', 'promedio', 'fecha_inscripcion',
                    'fecha_captura']
    list_filter = ['grupo']
    search_fields = ['alumno__matricula', 'alumno__nombre', 'grupo__periodo']
    inlines = [CalificacionUnidadInline]

    @admin.display(description='Calificación final')
    def promedio(self, calificacion):
        return calificacion.valor_promedio


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'rol', 'alumno']
    list_filter = ['rol']
    search_fields = ['usuario__username', 'alumno__matricula', 'alumno__nombre']