"""Gestión de usuarios del sistema y del acceso de los alumnos.

Las pantallas de alta, edición y contraseña comparten una sola plantilla
(`usuarios_form.html`) y el mismo esqueleto: mostrar el formulario, guardarlo si
es válido y volver al listado.
"""

from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import DeleteView, ListView

from ..forms import (AlumnoForm, AlumnosSinUsuario, PasswordForm,
                     UsuarioEdicionForm, UsuarioPersonalForm,
                     alumnos_sin_usuario, roles_que_pueden_asignar)
from ..models import Perfil
from ..permisos import RolRequeridoMixin, requiere_rol

ROLES_GESTION_USUARIOS = ('ADMINISTRADOR', 'COORDINADOR')
FORMULARIO = 'academico/usuarios_form.html'


class BaseUsuarios(RolRequeridoMixin):
    """Todo lo de usuarios exige ser administrador o coordinador."""

    roles_permitidos = ROLES_GESTION_USUARIOS
    template_name = 'academico/usuarios.html'


class UsuarioListView(BaseUsuarios, ListView):
    context_object_name = 'perfiles'
    template_name = 'academico/usuarios.html'

    def get_queryset(self):
        return (Perfil.objects
                .select_related('usuario', 'alumno')
                .order_by('rol', 'usuario__username'))


class UsuarioDeleteView(BaseUsuarios, DeleteView):
    """Elimina un usuario que no está asociado a un alumno."""

    model = User
    template_name = 'academico/confirmar_borrado.html'
    success_url = reverse_lazy('usuario_list')

    def dispatch(self, request, *args, **kwargs):
        usuario = self.get_object()
        perfil = Perfil.objects.filter(usuario=usuario).first()
        if perfil and perfil.alumno_id:
            messages.error(
                request,
                f'{usuario.username} es un alumno: da de baja al alumno desde '
                f'su catálogo para eliminar también su acceso.'
            )
            return redirect('usuario_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Usuario eliminado.')
        return super().form_valid(form)


def _pantalla_formulario(request, form_factory, titulo, exito, **extra):
    """Muestra el formulario y, si es válido, guarda y vuelve al listado.

    `form_factory` recibe los datos de la petición y devuelve el formulario,
    de modo que el mensaje de éxito se arma con lo que devolvió `form.save()`.
    """
    form = form_factory(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        guardado = form.save()
        messages.success(request, exito(guardado) if exito else '')
        return redirect('usuario_list')
    contexto = {
        'form': form,
        'titulo': titulo,
        'volver': reverse('usuario_list'),
        'sin_usuario': alumnos_sin_usuario().count(),
    }
    contexto.update(extra)
    return render(request, FORMULARIO, contexto)


def _usuario_por_id(pk):
    """Devuelve el User esté o no tenga Perfil (un superusuario puede no tenerlo)."""
    perfil = (Perfil.objects
              .select_related('usuario', 'alumno')
              .filter(usuario_id=pk)
              .first())
    if perfil is not None:
        return perfil.usuario
    return get_object_or_404(User, pk=pk)


@requiere_rol(*ROLES_GESTION_USUARIOS)
def usuario_redirect_alumno(request):
    """`/alumnos/nuevo/` apunta ahora a la pantalla de alta de alumnos."""
    return redirect(reverse('usuario_create_alumno'))


@requiere_rol(*ROLES_GESTION_USUARIOS)
def usuario_create_tipo(request):
    """Paso 1: elegir qué tipo de usuario se va a crear."""
    return render(request, 'academico/usuarios_tipo.html', {
        'sin_usuario': alumnos_sin_usuario().count(),
    })


@requiere_rol(*ROLES_GESTION_USUARIOS)
def usuario_create_alumno(request):
    """Alta de alumno: se crean el alumno, su usuario y su rol."""
    return _pantalla_formulario(
        request, AlumnoForm, 'Alta de alumno',
        lambda alumno: (f'Alumno {alumno.matricula} dado de alta. Ya puede '
                        f'iniciar sesión con su matrícula y la contraseña '
                        f'asignada.'))


@requiere_rol(*ROLES_GESTION_USUARIOS)
def usuario_create_alumno_existente(request):
    """Da de acceso a un alumno que ya existía sin usuario."""
    return _pantalla_formulario(
        request, AlumnosSinUsuario, 'Dar acceso a un alumno',
        lambda usuario: (f'{usuario.username} ya puede iniciar sesión como '
                         f'estudiante.'))


@requiere_rol(*ROLES_GESTION_USUARIOS)
def usuario_create_personal(request):
    """Alta de coordinador o administrador."""
    roles = roles_que_pueden_asignar(request.user)
    return _pantalla_formulario(
        request,
        lambda datos: UsuarioPersonalForm(datos, roles_permitidos=roles),
        'Alta de personal',
        lambda usuario: (f'Usuario {usuario.username} creado con el rol '
                         f'{usuario.perfil.rol}.'))


@requiere_rol(*ROLES_GESTION_USUARIOS)
def usuario_update(request, pk):
    """Cambia nombre, rol y estado de un usuario."""
    usuario = _usuario_por_id(pk)
    roles = roles_que_pueden_asignar(request.user)
    return _pantalla_formulario(
        request,
        lambda datos: UsuarioEdicionForm(datos, instance=usuario,
                                         roles_permitidos=roles),
        f'Editar usuario {usuario.username}',
        lambda usuario: f'Usuario {usuario.username} actualizado.',
        usuario=usuario,
        perfil=Perfil.objects.filter(usuario=usuario).first())


@requiere_rol(*ROLES_GESTION_USUARIOS)
def usuario_password(request, pk):
    """Asigna o cambia la contraseña de un usuario."""
    usuario = get_object_or_404(User.objects.select_related('perfil'), pk=pk)
    form = PasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.aplicar(usuario)
        messages.success(
            request, f'Contraseña de {usuario.username} actualizada.')
        return redirect('usuario_list')
    return render(request, FORMULARIO, {
        'form': form,
        'usuario': usuario,
        'titulo': f'Contraseña de {usuario.username}',
        'volver': reverse('usuario_list'),
    })
