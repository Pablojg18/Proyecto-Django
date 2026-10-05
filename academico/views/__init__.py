"""Vistas del sistema escolar agrupadas por responsabilidad."""

from .cardex import alumno_cardex, mi_cardex
from .carga import carga_de_alumno, mi_carga_academica
from .cuentas import CerrarSesion, IniciarSesion, index
from .catalogos import (AlumnoCreateView, AlumnoDeleteView, AlumnoListView,
                        AlumnoUpdateView, CarreraCreateView, CarreraDeleteView,
                        CarreraListView, CarreraUpdateView, GrupoCreateView,
                        GrupoDeleteView, GrupoListView, GrupoUpdateView,
                        MateriaCreateView, MateriaDeleteView, MateriaListView,
                        MateriaUpdateView, PeriodoActivarView,
                        PeriodoCreateView, PeriodoDeleteView, PeriodoListView,
                        PeriodoUpdateView)
from .inscripcion import (AlumnosParaInscribir, InscripcionCoordinador,
                         MiInscripcion)
from .usuarios import (UsuarioAlumnoCreateView, UsuarioAlumnoExistenteCreateView,
                       UsuarioDeleteView, UsuarioListView, UsuarioPasswordView,
                       UsuarioPersonalCreateView, UsuarioTipoView,
                       UsuarioUpdateView, usuario_redirect_alumno)

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
    'PeriodoListView', 'PeriodoCreateView', 'PeriodoUpdateView',
    'PeriodoDeleteView', 'PeriodoActivarView',
    'AlumnosParaInscribir', 'InscripcionCoordinador', 'MiInscripcion',
    'alumno_cardex', 'mi_cardex', 'carga_de_alumno', 'mi_carga_academica',
    'UsuarioListView', 'UsuarioTipoView', 'UsuarioAlumnoCreateView',
    'UsuarioAlumnoExistenteCreateView', 'UsuarioPersonalCreateView',
    'UsuarioUpdateView', 'UsuarioPasswordView', 'UsuarioDeleteView',
    'usuario_redirect_alumno',
]