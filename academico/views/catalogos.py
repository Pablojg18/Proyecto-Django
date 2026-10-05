"""Catálogos del sistema: alumnos, carreras, materias y grupos."""

from django.contrib import messages
from django.db.models import Count, ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import (CreateView, DeleteView, ListView,
                                  UpdateView, View)

from ..forms import (AlumnoForm, CarreraForm, GrupoForm, MateriaForm,
                     PeriodoForm)
from ..models import Alumno, Carrera, Grupo, Materia, Periodo
from ..permisos import RolRequeridoMixin

ROLES_CONTROL = ('ADMINISTRADOR', 'COORDINADOR')
ROLES_ADMIN = ('ADMINISTRADOR',)
ROLES_COORDINACION = ('ADMINISTRADOR', 'COORDINADOR')


class ListadoBase(RolRequeridoMixin, ListView):
    """Listado de un catálogo, con permisos de lectura."""

    roles_permitidos = ()
    context_object_name = 'objetos'


class FormularioConTitulo:
    """Añade a la plantilla el título de la pantalla y el enlace de regreso."""

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['titulo'] = self.titulo_pantalla()
        contexto['volver'] = str(self.success_url)
        return contexto


class AltaBase(RolRequeridoMixin, FormularioConTitulo, CreateView):
    """Alta de registros: exclusiva del administrador."""

    roles_permitidos = ()
    template_name = 'academico/form_generico.html'
    success_message = 'Registro creado correctamente.'

    def titulo_pantalla(self):
        return f'Alta de {self.model._meta.verbose_name}'

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return respuesta


class EdicionBase(RolRequeridoMixin, FormularioConTitulo, UpdateView):
    """Edición de registros."""

    roles_permitidos = ()
    template_name = 'academico/form_generico.html'
    success_message = 'Registro actualizado correctamente.'

    def titulo_pantalla(self):
        return f'Edición de {self.model._meta.verbose_name}'

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return respuesta


class BorradoBase(RolRequeridoMixin, DeleteView):
    """Baja de registros."""

    roles_permitidos = ()
    template_name = 'academico/confirmar_borrado.html'
    success_message = 'Registro eliminado correctamente.'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['volver'] = str(self.success_url)
        return contexto

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return respuesta


# --- Alumnos ---------------------------------------------------------------

class AlumnoListView(ListadoBase):
    model = Alumno
    form_class = AlumnoForm
    roles_permitidos = ROLES_CONTROL
    context_object_name = 'alumnos'
    template_name = 'academico/alumno_list.html'

    def get_queryset(self):
        return (Alumno.objects
                .select_related('carrera')
                .prefetch_related('calificaciones__grupo__materia'))


class AlumnoCreateView(AltaBase):
    model = Alumno
    form_class = AlumnoForm
    roles_permitidos = ROLES_ADMIN
    success_url = reverse_lazy('alumno_list')
    success_message = 'Alumno dado de alta con su usuario para iniciar sesión.'


class AlumnoUpdateView(EdicionBase):
    model = Alumno
    form_class = AlumnoForm
    roles_permitidos = ROLES_ADMIN
    success_url = reverse_lazy('alumno_list')
    success_message = 'Alumno actualizado.'


class AlumnoDeleteView(BorradoBase):
    model = Alumno
    roles_permitidos = ROLES_ADMIN
    success_url = reverse_lazy('alumno_list')
    success_message = 'Alumno eliminado.'


# --- Carreras --------------------------------------------------------------

class CarreraListView(ListadoBase):
    model = Carrera
    roles_permitidos = ROLES_CONTROL
    context_object_name = 'carreras'
    template_name = 'academico/carrera_list.html'

    def get_queryset(self):
        return Carrera.objects.annotate(
            total_materias=Count('materias'),
            total_alumnos=Count('alumnos'),
        )


class CarreraCreateView(AltaBase):
    model = Carrera
    form_class = CarreraForm
    roles_permitidos = ROLES_ADMIN
    success_url = reverse_lazy('carrera_list')


class CarreraUpdateView(EdicionBase):
    model = Carrera
    form_class = CarreraForm
    roles_permitidos = ROLES_ADMIN
    success_url = reverse_lazy('carrera_list')


class CarreraDeleteView(BorradoBase):
    model = Carrera
    roles_permitidos = ROLES_ADMIN
    success_url = reverse_lazy('carrera_list')


# --- Materias --------------------------------------------------------------

class MateriaListView(ListadoBase):
    model = Materia
    roles_permitidos = ROLES_CONTROL
    context_object_name = 'materias'
    template_name = 'academico/materia_list.html'

    def get_queryset(self):
        return (Materia.objects
                .select_related('carrera')
                .annotate(total_grupos=Count('grupos')))


class MateriaCreateView(AltaBase):
    model = Materia
    form_class = MateriaForm
    roles_permitidos = ROLES_ADMIN
    success_url = reverse_lazy('materia_list')


class MateriaUpdateView(EdicionBase):
    model = Materia
    form_class = MateriaForm
    roles_permitidos = ROLES_ADMIN
    success_url = reverse_lazy('materia_list')


class MateriaDeleteView(BorradoBase):
    model = Materia
    roles_permitidos = ROLES_ADMIN
    success_url = reverse_lazy('materia_list')


# --- Grupos ----------------------------------------------------------------

class GrupoListView(ListadoBase):
    model = Grupo
    roles_permitidos = ROLES_COORDINACION
    context_object_name = 'grupos'
    template_name = 'academico/grupo_list.html'

    def get_queryset(self):
        return (Grupo.objects
                .select_related('materia', 'materia__carrera', 'periodo')
                .order_by('-periodo__nombre', 'materia__codigo', 'turno',
                          'horario'))


class GrupoCreateView(AltaBase):
    model = Grupo
    form_class = GrupoForm
    roles_permitidos = ROLES_COORDINACION
    success_url = reverse_lazy('grupo_list')
    success_message = 'Grupo creado correctamente.'

    def get_initial(self):
        inicial = super().get_initial()
        actual = Periodo.actual()
        if actual:
            inicial['periodo'] = actual.pk
        return inicial


class GrupoUpdateView(EdicionBase):
    model = Grupo
    form_class = GrupoForm
    roles_permitidos = ROLES_COORDINACION
    success_url = reverse_lazy('grupo_list')
    success_message = 'Grupo actualizado correctamente.'


class GrupoDeleteView(BorradoBase):
    model = Grupo
    roles_permitidos = ROLES_COORDINACION
    success_url = reverse_lazy('grupo_list')
    success_message = 'Grupo eliminado correctamente.'


# --- Periodos --------------------------------------------------------------

class PeriodoListView(ListadoBase):
    model = Periodo
    roles_permitidos = ROLES_COORDINACION
    context_object_name = 'periodos'
    template_name = 'academico/periodo_list.html'

    def get_queryset(self):
        return (Periodo.objects
                .annotate(total_grupos=Count('grupos'))
                .order_by('-nombre'))


class PeriodoCreateView(AltaBase):
    model = Periodo
    form_class = PeriodoForm
    roles_permitidos = ROLES_COORDINACION
    success_url = reverse_lazy('periodo_list')
    success_message = 'Periodo creado correctamente.'


class PeriodoUpdateView(EdicionBase):
    model = Periodo
    form_class = PeriodoForm
    roles_permitidos = ROLES_COORDINACION
    success_url = reverse_lazy('periodo_list')
    success_message = 'Periodo actualizado correctamente.'


class PeriodoDeleteView(BorradoBase):
    model = Periodo
    roles_permitidos = ROLES_COORDINACION
    success_url = reverse_lazy('periodo_list')
    success_message = 'Periodo eliminado correctamente.'

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                'El periodo tiene grupos o inscripciones registradas: '
                'no se puede eliminar.')
            return redirect('periodo_list')


class PeriodoActivarView(RolRequeridoMixin, View):
    """Deja un periodo como vigente; solo uno puede estar activo."""

    roles_permitidos = ROLES_COORDINACION
    http_method_names = ['post']

    def post(self, request):
        periodo = get_object_or_404(Periodo, pk=request.POST.get('periodo'))
        periodo.activar()
        messages.success(request, f'El periodo vigente ahora es {periodo}.')
        destino = request.POST.get('siguiente') or '/'
        if not url_has_allowed_host_and_scheme(destino, allowed_hosts=None):
            destino = '/'
        return redirect(destino)