"""Vida académica de un alumno: inscripción, carga y cardex.

Un solo módulo porque las tres pantallas comparten lo mismo: quién es el alumno
de la petición, cómo se validan las materias que puede tomar y cómo se
presentan sus calificaciones.
"""

from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from ..forms import (CalificacionUnidadFormSet, FiltroAlumnosForm,
                     InscripcionForm, grupos_inscribibles)
from ..models import Alumno, CalificacionUnidad, Periodo
from ..permisos import perfil_de, requiere_rol
from ..services import ErrorInscripcion, desinscribir_alumno, inscribir_alumno

COORDINACION = ('ADMINISTRADOR', 'COORDINADOR')

INSCRIPCION = 'academico/inscripcion.html'
CARGA = 'academico/carga_academica.html'
CARDEX = 'academico/alumno_cardex.html'


def _alumno_de_la_sesion(request):
    """Alumno del usuario conectado, o None si no aplica."""
    perfil = perfil_de(request.user)
    return perfil.alumno if perfil else None


def _alumno_por_matricula(matricula):
    return get_object_or_404(
        Alumno.objects.select_related('carrera'), matricula=matricula)


# --- Inscripción -----------------------------------------------------------

@requiere_rol(*COORDINACION)
def alumnos_para_inscribir(request):
    """Paso 1 del coordinador: elegir al alumno al que inscribir."""
    filtro = FiltroAlumnosForm(request.GET or None)
    alumnos = filtro.aplicar(
        Alumno.objects.select_related('carrera')).order_by('matricula')

    return render(request, 'academico/inscripcion_alumnos.html', {
        'alumnos': alumnos,
        'filtro': filtro,
        'periodo_actual': Periodo.actual(),
    })


@requiere_rol(*COORDINACION)
def inscripcion_alumno(request, matricula):
    """Paso 2 del coordinador: inscribir o quitar materias a un alumno."""
    return _pantalla_inscripcion(request, _alumno_por_matricula(matricula),
                                 forzar=True)


@requiere_rol('ESTUDIANTE')
def mi_inscripcion(request):
    """Inscripción del estudiante: una sola vez por periodo."""
    return _pantalla_inscripcion(request, _alumno_de_la_sesion(request),
                                 forzar=False)


def _sin_alumno(request):
    """El usuario no está asociado a un alumno del catálogo."""
    messages.error(request, 'Tu usuario no tiene un alumno asociado.')
    return redirect('index')


def _pantalla_inscripcion(request, alumno, forzar):
    """Muestra y procesa la pantalla de inscripción.

    Los dos formularios de la pantalla (inscribir y dar de baja) se distinguen
    por el botón pulsado, en el campo ``accion``. Antes se distinguían por las
    casillas de "quitar" y, como el botón enviaba su propio formulario, la baja
    nunca llegaba a la vista y el alta se quejaba de "campo obligatorio".

    ``forzar=True`` es el uso del coordinador, que puede Inscribir y quitar
    en cualquier momento; el estudiante solo se inscribe una vez por periodo.
    """
    if alumno is None:
        return _sin_alumno(request)

    periodo = Periodo.actual()
    opciones = grupos_inscribibles(alumno, periodo)
    contexto = {
        'alumno': alumno,
        'periodo_actual': periodo,
        'carga_actual': list(alumno.carga_academica()),
        'forzar': forzar,
        'puede_inscribirse': forzar or not alumno.tiene_carga_activa,
        'titulo': ('Inscribir alumno' if forzar
                   else 'Inscripción de materias'),
        'url_carga': (reverse('carga_de_alumno', args=[alumno.matricula])
                      if forzar else reverse('mi_carga_academica')),
        'form': InscripcionForm(opciones=opciones, alumno=alumno),
    }

    if request.method != 'POST':
        return render(request, INSCRIPCION, contexto)

    if request.POST.get('accion') == 'quitar':
        if not forzar:
            messages.error(
                request, 'Solo tu coordinador puede dar de baja una materia.')
        else:
            total = desinscribir_alumno(
                alumno,
                alumno.calificaciones.filter(pk__in=request.POST.getlist('quitar')))
            messages.success(request,
                             f'Se dieron de baja {total} inscripción(es).')
        return redirect(request.path)

    if not contexto['puede_inscribirse']:
        messages.error(
            request,
            f'Ya te inscribiste en el periodo {periodo}: solo puedes '
            f'inscribirte una vez por periodo. Si necesitas cambios, '
            f'pídele a tu coordinador.')
        return render(request, INSCRIPCION, contexto)

    form = contexto['form'] = InscripcionForm(
        request.POST, opciones=opciones, alumno=alumno)
    if not form.is_valid():
        return render(request, INSCRIPCION, contexto)

    try:
        creadas = inscribir_alumno(
            alumno, form.cleaned_data['grupos'], forzar=forzar)
    except ErrorInscripcion as error:
        messages.error(request, str(error))
        return render(request, INSCRIPCION, contexto)

    messages.success(
        request, f'{len(creadas)} materia(s) inscritas a {alumno.matricula}.')
    return redirect(request.path)


# --- Carga académica -------------------------------------------------------

@requiere_rol(*COORDINACION)
def carga_de_alumno(request, matricula):
    """Carga académica de cualquier alumno (coordinador o administrador)."""
    return render(request, CARGA,
                  _contexto_carga(_alumno_por_matricula(matricula)))


@requiere_rol('ESTUDIANTE')
def mi_carga_academica(request):
    """Carga académica del estudiante que inició sesión."""
    alumno = _alumno_de_la_sesion(request)
    if alumno is None:
        return _sin_alumno(request)
    return render(request, CARGA, _contexto_carga(alumno))


def _contexto_carga(alumno):
    """Solo la carga del periodo vigente; el historial vive en el cardex."""
    return {
        'alumno': alumno,
        'carga_actual': list(alumno.carga_academica()),
        'materias_cursadas': alumno.materias_cursadas,
        'creditos_en_curso': alumno.creditos_en_curso,
        'creditos_acumulados': alumno.creditos_acumulados,
        'promedio_general': alumno.promedio_general,
        'materias_aprobadas': len(alumno.materias_aprobadas),
        'materias_reprobadas': len(alumno.materias_reprobadas),
        'periodo_activo': Periodo.actual(),
    }


# --- Cardex ----------------------------------------------------------------

@requiere_rol(*COORDINACION)
def alumno_cardex(request, matricula):
    """Captura por unidad del historial y cardex de un alumno."""
    alumno = _alumno_por_matricula(matricula)
    _sincronizar_unidades(alumno)

    unidades = (CalificacionUnidad.objects
                .filter(calificacion__alumno=alumno)
                .select_related('calificacion',
                                'calificacion__grupo',
                                'calificacion__grupo__materia',
                                'calificacion__grupo__periodo')
                .order_by('-calificacion__grupo__periodo__nombre',
                          'calificacion__grupo__materia__codigo',
                          'numero_unidad'))

    formset = CalificacionUnidadFormSet(
        request.POST if request.method == 'POST' else None,
        queryset=unidades, prefix='unidades',
    )
    if request.method == 'POST' and formset.is_valid():
        with transaction.atomic():
            formset.save()
            _actualizar_fechas_captura(alumno)
        messages.success(
            request, f'Se guardó el cardex de {alumno.matricula}.')
        return redirect('alumno_cardex', matricula=alumno.matricula)

    return render(request, CARDEX, _contexto_cardex(alumno, formset))


@requiere_rol('ESTUDIANTE')
def mi_cardex(request):
    """El estudiante solo consulta su propio historial, sin editarlo."""
    alumno = _alumno_de_la_sesion(request)
    if alumno is None:
        return _sin_alumno(request)
    return render(request, CARDEX, _contexto_cardex(alumno, solo_lectura=True))


def _sincronizar_unidades(alumno):
    """Deja una fila de calificación por cada unidad declarada por la materia.

    Se ejecuta antes de mostrar o guardar el cardex: si cambia el número de
    unidades de una materia, se crean las que falten y se borran las que ya no
    existen (su calificación dejaría de tener sentido).
    """
    for calificacion in (alumno.calificaciones
                         .select_related('grupo__materia')):
        unidades = calificacion.grupo.materia.unidades
        existentes = set(calificacion.calificaciones_unidad
                         .values_list('numero_unidad', flat=True))
        for numero in range(1, unidades + 1):
            if numero not in existentes:
                CalificacionUnidad.objects.create(
                    calificacion=calificacion, numero_unidad=numero)
        sobrantes = existentes - set(range(1, unidades + 1))
        if sobrantes:
            calificacion.calificaciones_unidad.filter(
                numero_unidad__in=sobrantes).delete()


def _actualizar_fechas_captura(alumno):
    """Fecha de captura de cada inscripción: hoy si tiene calificación, si no vacía."""
    hoy = timezone.localdate()
    for calificacion in alumno.calificaciones.select_related('grupo__materia'):
        calificacion.fecha_captura = hoy if calificacion.esta_calificada else None
        calificacion.save(update_fields=['fecha_captura'])


def _contexto_cardex(alumno, formset=None, solo_lectura=False):
    historial = list(alumno.historial_academico)

    return {
        'alumno': alumno,
        'formset': formset,
        'solo_lectura': solo_lectura,
        'calificaciones': historial,
        'historial_completado': [c for c in historial if c.esta_calificada],
        'filas_captura': _filas_captura(formset, historial),
        'materias_cursadas': alumno.materias_cursadas,
        'materias_aprobadas': len(alumno.materias_aprobadas),
        'materias_reprobadas': len(alumno.materias_reprobadas),
        'creditos_acumulados': alumno.creditos_acumulados,
        'creditos_en_curso': alumno.creditos_en_curso,
        'promedio_general': alumno.promedio_general,
        'aprobada_minimo': settings.CALIFICACION_APROBADA,
        'calificacion_maxima': settings.CALIFICACION_MAXIMA,
    }


def _filas_captura(formset, historial):
    """Agrupa los formularios de unidades por inscripción, con su promedio.

    El promedio se calcula con lo que hay en la pantalla —lo tecleado si se
    acaba de enviar, o lo guardado si es la primera vez que se abre— para que
    la columna "Calificación final" nunca se quede en blanco o en "Sin
    calificar" cuando las unidades ya están capturadas.
    """
    if formset is None:
        return []

    forms_por_calificacion = {}
    for form in formset:
        clave = form.instance.calificacion_id
        forms_por_calificacion.setdefault(clave, []).append(form)

    filas = []
    for calificacion in historial:
        forms = forms_por_calificacion.get(calificacion.pk)
        if not forms:
            continue
        valores = [_valor_de_form(form) for form in forms]
        promedio = _promedio(valores)
        filas.append({
            'calificacion': calificacion,
            'forms': forms,
            'valor': promedio,
            'aprobada': _es_aprobada(promedio),
            # "Completa" solo si todas las unidades tienen una calificación
            # válida: una unidad con error deja la materia incompleta.
            'completa': all(valor is not None for valor in valores),
        })
    return filas


def _valor_de_form(form):
    """Calificación de una unidad: la guardada o la que pasó la validación.

    Una unidad con error se cuenta como vacía, así el promedio que se muestra
    corresponde a lo que realmente se va a guardar.
    """
    if not hasattr(form, 'cleaned_data'):
        return form.instance.valor
    return form.cleaned_data.get('valor')


def _promedio(valores):
    capturados = [valor for valor in valores if valor is not None]
    if not capturados:
        return None
    return (sum(capturados) / Decimal(len(capturados))).quantize(Decimal('0.0'))


def _es_aprobada(promedio):
    return (promedio is not None
            and settings.CALIFICACION_APROBADA <= promedio
            <= settings.CALIFICACION_MAXIMA)
