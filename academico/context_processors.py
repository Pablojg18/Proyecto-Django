from .permisos import perfil_de


def rol_actual(request):
    """Perfil y banderas de rol para las plantillas (menú por rol)."""
    perfil = perfil_de(request.user)
    return {
        'perfil': perfil,
        'es_admin': bool(perfil and perfil.rol == 'ADMINISTRADOR')
        or request.user.is_superuser,
        'es_coordinador': bool(perfil and perfil.rol == 'COORDINADOR'),
        'es_estudiante': bool(perfil and perfil.rol == 'ESTUDIANTE'),
    }