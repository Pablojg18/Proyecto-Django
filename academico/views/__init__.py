"""Punto único de importación de las vistas.

Las vistas viven en cuatro módulos por responsabilidad (`alumno`, `catalogos`,
`cuentas`, `usuarios`) y aquí se reexportan para que `urls.py` y el resto del
proyecto usen `academico.views.<nombre>`.
"""

from .alumno import (alumno_cardex, alumnos_para_inscribir, carga_de_alumno,
                     inscripcion_alumno, mi_carga_academica, mi_cardex,
                     mi_inscripcion)
from .catalogos import (AlumnoCreateView, AlumnoDeleteView, AlumnoListView,
                        AlumnoUpdateView, CarreraCreateView, CarreraDeleteView,
                        CarreraListView, CarreraUpdateView, GrupoCreateView,
                        GrupoDeleteView, GrupoListView, GrupoUpdateView,
                        MateriaCreateView, MateriaDeleteView, MateriaListView,
                        MateriaUpdateView, PeriodoActivarView,
                        PeriodoCreateView, PeriodoDeleteView, PeriodoListView,
                        PeriodoUpdateView)
from .cuentas import CerrarSesion, IniciarSesion, index
from .usuarios import (UsuarioDeleteView, UsuarioListView,
                       usuario_create_alumno,
                       usuario_create_alumno_existente,
                       usuario_create_personal, usuario_create_tipo,
                       usuario_password, usuario_redirect_alumno,
                       usuario_update)

__all__ = [
    'index', 'IniciarSesion', 'CerrarSesion',
    'AlumnoListView', 'AlumnoCreateView', 'AlumnoUpdateView',
    'AlumnoDeleteView',
    'CarreraListView', 'CarreraCreateView', 'CarreraUpdateView',
    'CarreraDeleteView',
    'MateriaListView', 'MateriaCreateView', 'MateriaUpdateView',
    'MateriaDeleteView',
    'GrupoListView', 'GrupoCreateView', 'GrupoUpdateView', 'GrupoDeleteView',
    'PeriodoListView', 'PeriodoCreateView', 'PeriodoUpdateView',
    'PeriodoDeleteView', 'PeriodoActivarView',
    'alumnos_para_inscribir', 'inscripcion_alumno', 'mi_inscripcion',
    'alumno_cardex', 'mi_cardex', 'carga_de_alumno', 'mi_carga_academica',
    'UsuarioListView', 'usuario_create_tipo', 'usuario_create_alumno',
    'usuario_create_alumno_existente', 'usuario_create_personal',
    'usuario_update', 'usuario_password', 'UsuarioDeleteView',
    'usuario_redirect_alumno',
]
