"""Inscripción de alumnos: por parte del coordinador y del propio estudiante."""

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView, View

from ..forms import FiltroAlumnosForm, InscripcionForm, grupos_inscribibles
from ..models import Alumno
from ..permisos import RolRequeridoMixin, perfil_de
from ..services import ErrorInscripcion, desinscribir_alumno, inscribir_alumno

ROLES_ESTUDIANTE = ('ESTUDIANTE',)
ROLES_COORDINADOR = ('COORDINADOR',)


class AlumnosParaInscribir(RolRequeridoMixin, ListView):
    """Paso 1 del coordinador: elegir al alumno a inscribir."""

    model = Alumno
    roles_permitidos = ROLES_COORDINADOR
    template_name = 'academico/inscripcion_alumnos.html'
    context_object_name = 'alumnos'

    def get_queryset(self):
        queryset = Alumno.objects.select_related('carrera').order_by('matricula')
        self.filtro = FiltroAlumnosForm(self.request.GET or None)
        if self.filtro.is_valid():
            busqueda = self.filtro.cleaned_data.get('q')
            carrera = self.filtro.cleaned_data.get('carrera')
            if busqueda:
                queryset = queryset.filter(
                    Q(matricula__icontains=busqueda)
                    | Q(nombre__icontains=busqueda)
                    | Q(carrera__nombre__icontains=busqueda)
                )
            if carrera:
                queryset = queryset.filter(carrera=carrera)
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['filtro'] = self.filtro
        contexto['periodo_actual'] = settings.PERIODO_ACTUAL
        return contexto


class InscripcionBase(RolRequeridoMixin, View):
    """Pantalla de inscripción reutilizada por coordinador y estudiante.

    ``forzar=True`` permite al coordinador registrar inscripciones aunque el
    alumno ya tenga carga académica activa en el periodo vigente.
    """

    roles_permitidos = ()
    forzar = False

    def get_alumno(self, request, *args, **kwargs):
        raise NotImplementedError

    def get_context_data(self, alumno, form=None, opciones=None):
        if opciones is None:
            opciones = grupos_inscribibles(alumno, settings.PERIODO_ACTUAL)
        if form is None:
            form = InscripcionForm(opciones=opciones)
        carga = list(alumno.carga_academica())
        return {
            'alumno': alumno,
            'form': form,
            'opciones': opciones,
            'carga_actual': carga,
            'quitar_ids': [c.pk for c in carga],
            'periodo_actual': settings.PERIODO_ACTUAL,
            'forzar': self.forzar,
            'titulo': ('Inscribir alumno' if self.forzar
                       else 'Inscripción de materias'),
        }

    def get(self, request, *args, **kwargs):
        alumno = self.get_alumno(request, *args, **kwargs)
        return render(request, 'academico/inscripcion.html',
                      self.get_context_data(alumno))

    def post(self, request, *args, **kwargs):
        alumno = self.get_alumno(request, *args, **kwargs)

        if self.forzar and 'quitar' in request.POST:
            return self.quitar_inscripciones(request, alumno)

        opciones = grupos_inscribibles(alumno, settings.PERIODO_ACTUAL)
        form = InscripcionForm(request.POST, opciones=opciones)
        if form.is_valid():
            try:
                creadas = inscribir_alumno(
                    alumno, form.cleaned_data['grupos'], forzar=self.forzar)
            except ErrorInscripcion as error:
                messages.error(request, str(error))
            else:
                messages.success(
                    request,
                    f'{len(creadas)} materia(s) inscritas a {alumno.matricula}.'
                )
                return redirect(request.path)
        else:
            for error in form.errors.get('grupos', []):
                messages.error(request, error)

        return render(request, 'academico/inscripcion.html',
                      self.get_context_data(alumno, form, opciones))

    def quitar_inscripciones(self, request, alumno):
        seleccion = request.POST.getlist('quitar')
        calificaciones = alumno.calificaciones.filter(pk__in=seleccion)
        total = desinscribir_alumno(alumno, calificaciones)
        messages.success(
            request, f'Se dieron de baja {total} inscripción(es) del periodo.')
        return redirect(request.path)


class InscripcionCoordinador(InscripcionBase):
    """Paso 2 del coordinador: elegir las materias de un alumno."""

    roles_permitidos = ROLES_COORDINADOR
    forzar = True

    def get_alumno(self, request, matricula):
        return get_object_or_404(
            Alumno.objects.select_related('carrera'), matricula=matricula)


class MiInscripcion(InscripcionBase):
    """Inscripción del estudiante sobre su propio registro."""

    roles_permitidos = ROLES_ESTUDIANTE
    forzar = False

    def get_alumno(self, request):
        perfil = perfil_de(request.user)
        if perfil is None or perfil.alumno_id is None:
            raise PermissionDenied('El usuario no tiene un alumno asociado.')
        return get_object_or_404(
            Alumno.objects.select_related('carrera'), pk=perfil.alumno_id)