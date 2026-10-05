"""Gestión de usuarios del sistema y del acceso de los alumnos."""

from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import DeleteView, ListView, View

from ..forms import (AlumnoForm, AlumnosSinUsuario, PasswordForm,
                     UsuarioEdicionForm, UsuarioPersonalForm,
                     roles_que_pueden_asignar)
from ..models import Alumno, Perfil
from ..permisos import RolRequeridoMixin, requiere_rol

ROLES_GESTION_USUARIOS = ('ADMINISTRADOR', 'COORDINADOR')


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


class UsuarioTipoView(BaseUsuarios, View):
    """Paso 1: elegir qué tipo de usuario se va a crear."""

    def get(self, request):
        return render(request, 'academico/usuarios_tipo.html', {
            'sin_usuario': Alumno.objects.filter(
                perfil_de_alumno__isnull=True).count(),
        })


class UsuarioAlumnoCreateView(BaseUsuarios, View):
    """Alta de alumno: se crean el alumno, su usuario y su rol."""

    def get(self, request):
        return self.render_form(AlumnoForm())

    def post(self, request):
        form = AlumnoForm(request.POST)
        if form.is_valid():
            alumno = form.save()
            messages.success(
                request,
                f'Alumno {alumno.matricula} dado de alta. Ya puede iniciar '
                f'sesión con su matrícula y la contraseña asignada.'
            )
            return redirect('usuario_list')
        return self.render_form(form)

    def render_form(self, form):
        return render(self.request, 'academico/usuarios_alumno.html', {
            'form': form,
            'titulo': 'Alta de alumno',
            'volver': reverse('usuario_list'),
            'sin_usuario': Alumno.objects.filter(
                perfil_de_alumno__isnull=True).count(),
        })


class UsuarioAlumnoExistenteCreateView(BaseUsuarios, View):
    """Da de acceso a un alumno que ya existía sin usuario."""

    def get(self, request):
        return self.render_form(AlumnosSinUsuario())

    def post(self, request):
        form = AlumnosSinUsuario(request.POST)
        if form.is_valid():
            usuario = form.save()
            messages.success(
                request,
                f'{usuario.username} ya puede iniciar sesión como estudiante.'
            )
            return redirect('usuario_list')
        return self.render_form(form)

    def render_form(self, form):
        return render(self.request, 'academico/usuarios_alumno_existente.html',
                      {'form': form, 'titulo': 'Dar acceso a un alumno',
                       'volver': reverse('usuario_list')})


class UsuarioPersonalCreateView(BaseUsuarios, View):
    """Alta de coordinador o administrador."""

    def get(self, request):
        return self.render_form(self.form_vacio())

    def post(self, request):
        form = self.form_con_datos(request.POST)
        if form.is_valid():
            usuario = form.save()
            messages.success(
                request,
                f'Usuario {usuario.username} creado con el rol '
                f'{form.cleaned_data["rol"]}.'
            )
            return redirect('usuario_list')
        return self.render_form(form)

    def form_vacio(self):
        return self.form_con_datos()

    def form_con_datos(self, data=None):
        return UsuarioPersonalForm(
data, roles_permitidos=roles_que_pueden_asignar(self.request.user))

    def render_form(self, form):
        return render(self.request, 'academico/usuarios_personal.html',
                      {'form': form, 'titulo': 'Alta de personal',
                       'volver': reverse('usuario_list')})


class UsuarioUpdateView(BaseUsuarios, View):
    """Cambia nombre, rol y estado de un usuario."""

    def get(self, request, pk):
        usuario = self.usuario(pk)
        return self.render_form(self.form_con_datos(usuario=usuario), usuario)

    def post(self, request, pk):
        usuario = self.usuario(pk)
        form = self.form_con_datos(request.POST, usuario=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, f'Usuario {usuario.username} actualizado.')
            return redirect('usuario_list')
        return self.render_form(form, usuario)

    def usuario(self, pk):
        perfil = (Perfil.objects
                  .select_related('usuario', 'alumno')
                  .filter(usuario_id=pk)
                  .first())
        if perfil is not None:
            return perfil.usuario
        return get_object_or_404(User, pk=pk)

    def form_con_datos(self, data=None, usuario=None):
        return UsuarioEdicionForm(
            data, instance=usuario,
            roles_permitidos=roles_que_pueden_asignar(self.request.user))

    def render_form(self, form, usuario=None):
        perfil = Perfil.objects.filter(usuario=usuario).first()
        return render(self.request, 'academico/usuarios_edicion.html', {
            'form': form,
            'usuario': usuario,
            'perfil': perfil,
            'titulo': f'Editar usuario {usuario.username}',
            'volver': reverse('usuario_list'),
        })


class UsuarioPasswordView(BaseUsuarios, View):
    """Asigna o cambia la contraseña de un usuario."""

    def get(self, request, pk):
        return self.render_form(self.usuario(pk))

    def post(self, request, pk):
        usuario = self.usuario(pk)
        form = PasswordForm(request.POST)
        if form.is_valid():
            form.aplicar(usuario)
            messages.success(
                request, f'Contraseña de {usuario.username} actualizada.')
            return redirect('usuario_list')
        return self.render_form(usuario, form)

    def usuario(self, pk):
        return get_object_or_404(User.objects.select_related('perfil'), pk=pk)

    def render_form(self, usuario, form=None):
        return render(self.request, 'academico/usuarios_password.html', {
            'form': form or PasswordForm(),
            'usuario': usuario,
            'titulo': f'Contraseña de {usuario.username}',
            'volver': reverse('usuario_list'),
        })


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


@requiere_rol(*ROLES_GESTION_USUARIOS)
def usuario_redirect_alumno(request):
    """`/alumnos/nuevo/` apunta ahora a la pantalla de alta de alumnos."""
    return redirect(reverse('usuario_create_alumno'))
