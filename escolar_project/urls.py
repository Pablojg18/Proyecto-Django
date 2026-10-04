"""Rutas del sistema escolar."""

from django.contrib import admin
from django.urls import path
from academico import views

urlpatterns = [
    # Sesión
    path('accounts/login/', views.IniciarSesion.as_view(), name='login'),
    path('accounts/logout/', views.CerrarSesion.as_view(), name='logout'),

    # Portada
    path('', views.index, name='index'),

    # Catálogo de alumnos
    path('alumnos/', views.AlumnoListView.as_view(), name='alumno_list'),
    path('alumnos/nuevo/', views.AlumnoCreateView.as_view(),
         name='alumno_create'),
    path('alumnos/<str:pk>/editar/', views.AlumnoUpdateView.as_view(),
         name='alumno_update'),
    path('alumnos/<str:pk>/eliminar/', views.AlumnoDeleteView.as_view(),
         name='alumno_delete'),
    path('alumnos/<str:matricula>/cardex/', views.alumno_cardex,
         name='alumno_cardex'),
    path('alumnos/<str:matricula>/carga/', views.carga_de_alumno,
         name='carga_de_alumno'),

    # Catálogo de carreras
    path('carreras/', views.CarreraListView.as_view(), name='carrera_list'),
    path('carreras/nuevo/', views.CarreraCreateView.as_view(),
         name='carrera_create'),
    path('carreras/<str:pk>/editar/', views.CarreraUpdateView.as_view(),
         name='carrera_update'),
    path('carreras/<str:pk>/eliminar/', views.CarreraDeleteView.as_view(),
         name='carrera_delete'),

    # Catálogo de materias
    path('materias/', views.MateriaListView.as_view(), name='materia_list'),
    path('materias/nuevo/', views.MateriaCreateView.as_view(),
         name='materia_create'),
    path('materias/<str:pk>/editar/', views.MateriaUpdateView.as_view(),
         name='materia_update'),
    path('materias/<str:pk>/eliminar/', views.MateriaDeleteView.as_view(),
         name='materia_delete'),

    # Catálogo de grupos
    path('grupos/', views.GrupoListView.as_view(), name='grupo_list'),
    path('grupos/nuevo/', views.GrupoCreateView.as_view(), name='grupo_create'),
    path('grupos/<str:pk>/editar/', views.GrupoUpdateView.as_view(),
         name='grupo_update'),
    path('grupos/<str:pk>/eliminar/', views.GrupoDeleteView.as_view(),
         name='grupo_delete'),

    # Inscripción
    path('inscripcion/', views.MiInscripcion.as_view(), name='mi_inscripcion'),
    path('coordinacion/inscripcion/', views.AlumnosParaInscribir.as_view(),
         name='inscripcion_alumnos'),
    path('coordinacion/inscripcion/<str:matricula>/',
         views.InscripcionCoordinador.as_view(), name='inscripcion_alumno'),

    # Carga académica del estudiante
    path('mi-carga-academica/', views.mi_carga_academica,
         name='mi_carga_academica'),

    # Administración de Django (reservada a personal con permisos de staff)
    path('admin/', admin.site.urls),
]