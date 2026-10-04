"""Control de acceso por rol: administrador, coordinador y estudiante."""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect

from .models import Perfil

TODOS_LOS_ROLES = ('ADMINISTRADOR', 'COORDINADOR', 'ESTUDIANTE')


def perfil_de(usuario):
    """Perfil del usuario o None si todavía no tiene rol asignado."""
    if not usuario.is_authenticated:
        return None
    return Perfil.objects.filter(usuario=usuario).first()


def rol_de(usuario):
    """Rol efectivo del usuario; un superusuario actúa como administrador."""
    if not usuario.is_authenticated:
        return None
    if usuario.is_superuser:
        return 'ADMINISTRADOR'
    perfil = perfil_de(usuario)
    return perfil.rol if perfil else None


def sin_permiso(request):
    messages.error(
        request,
        'No tienes permiso para realizar esta operación con tu rol actual.'
    )
    return redirect('index')


def requiere_rol(*roles):
    """Decorador para vistas de función: exige sesión iniciada y uno de los roles."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.is_superuser:
                return vista(request, *args, **kwargs)
            if rol_de(request.user) not in roles:
                return sin_permiso(request)
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


class RolRequeridoMixin:
    """Control de acceso equivalente a `requiere_rol` para vistas de clase."""

    roles_permitidos = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        if rol_de(request.user) not in self.roles_permitidos:
            return sin_permiso(request)
        return super().dispatch(request, *args, **kwargs)


def es_alumno_del_usuario(usuario, alumno):
    """True si el usuario es ese alumno, o si tiene alcance total."""
    if usuario.is_superuser:
        return True
    perfil = perfil_de(usuario)
    return bool(perfil and perfil.alumno_id == alumno.pk)