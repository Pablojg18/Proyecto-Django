"""Vistas del sistema escolar agrupadas por responsabilidad."""

from .cardex import alumno_cardex
from .carga import carga_de_alumno, mi_carga_academica
from .cuentas import CerrarSesion, IniciarSesion, index
from .catalogos import (AlumnoCreateView, AlumnoDeleteView, AlumnoListView,
                        AlumnoUpdateView, CarreraCreateView, CarreraDeleteView,
                        CarreraListView, CarreraUpdateView, GrupoCreateView,
                        GrupoDeleteView, GrupoListView, GrupoUpdateView,
                        MateriaCreateView, MateriaDeleteView, MateriaListView,
                        MateriaUpdateView)
from .inscripcion import (AlumnosParaInscribir, InscripcionCoordinador,
                          MiInscripcion)

__all__ = [
    'index',
    'IniciarSesion', 'CerrarSesion',
    'AlumnoListView', 'AlumnoCreateView', 'AlumnoUpdateView',
    'AlumnoDeleteView',
    'CarreraListView', 'CarreraCreateView', 'CarreraUpdateView',
    'CarreraDeleteView',
    'MateriaListView', 'MateriaCreateView', 'MateriaUpdateView',
    'MateriaDeleteView',
    'GrupoListView', 'GrupoCreateView', 'GrupoUpdateView', 'GrupoDeleteView',
    'AlumnosParaInscribir', 'InscripcionCoordinador', 'MiInscripcion',
    'alumno_cardex', 'carga_de_alumno', 'mi_carga_academica',
]