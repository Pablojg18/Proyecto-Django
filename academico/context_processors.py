from .models import Periodo
from .permisos import perfil_de


def rol_actual(request):
    """Perfil y banderas de rol para las plantillas (menú por rol)."""
    perfil = perfil_de(request.user)
    es_admin = bool(perfil and perfil.rol == 'ADMINISTRADOR')
    es_coordinador = bool(perfil and perfil.rol == 'COORDINADOR')
    return {
        'perfil': perfil,
        'es_admin': es_admin or request.user.is_superuser,
        'es_coordinador': es_coordinador,
        'es_administracion': es_admin or es_coordinador
        or request.user.is_superuser,
        'es_estudiante': bool(perfil and perfil.rol == 'ESTUDIANTE'),
        'periodo_activo': Periodo.actual(),
        'periodos': Periodo.objects.order_by('-nombre'),
    }