"""Reglas de negocio de la inscripción de alumnos a grupos."""

from django.db import transaction
from django.db.models import F

from .models import Calificacion, CalificacionUnidad, Grupo, Periodo


class ErrorInscripcion(Exception):
    """Se lanza cuando una inscripción no cumple las reglas del sistema."""


def inscribir_alumno(alumno, grupos, forzar=False):
    """Inscribe al alumno en los grupos indicados.

    ``forzar=True`` (uso del coordinador) omite el bloqueo por carga académica
    activa, de modo que el coordinador siempre puede registrar inscripciones.

    Devuelve la lista de ``Calificacion`` creadas. Si alguna no cumple las
    reglas se lanza ``ErrorInscripcion`` y no se guarda nada.
    """
    grupos = list(grupos)
    if not grupos:
        return []

    periodo = Periodo.actual()
    if periodo is None:
        raise ErrorInscripcion(
            'No hay ningún periodo registrado: la inscripción está cerrada.')
    if not forzar and alumno.tiene_carga_activa:
        raise ErrorInscripcion(
            f'{alumno.matricula} ya se inscribió en el periodo {periodo}.'
        )

    # Un grupo no puede impartirse a la misma hora que otro del mismo alumno.
    # Los grupos en los que ya está inscrito no cuentan: esos avisan antes con
    # el error de materia ya cursada.
    ya_inscritos = set(alumno.calificaciones
                       .filter(grupo__in=grupos)
                       .values_list('grupo_id', flat=True))
    nuevos = [grupo for grupo in grupos if grupo.pk not in ya_inscritos]
    for i, grupo in enumerate(nuevos):
        for otro in nuevos[i + 1:]:
            if grupo.se_choca_con(otro):
                raise ErrorInscripcion(
                    f'{grupo.materia.codigo} ({grupo.horario}) y '
                    f'{otro.materia.codigo} ({otro.horario}) se imparten a la '
                    f'misma hora.'
                )
    propio = alumno.choca_con_sus_grupos(nuevos)
    if propio is not None:
        raise ErrorInscripcion(
            f'El horario choca con {propio.materia.codigo} '
            f'({propio.horario}), que {alumno.matricula} ya tiene inscrita.'
        )

    creadas = []
    with transaction.atomic():
        for grupo in grupos:
            bloqueado = Grupo.objects.select_for_update().get(pk=grupo.pk)
            materia = bloqueado.materia

            if bloqueado.periodo_id != periodo.pk:
                raise ErrorInscripcion(
                    f'El grupo de {materia.nombre} pertenece al periodo '
                    f'{bloqueado.periodo} y la inscripción está abierta para '
                    f'{periodo}.'
                )
            if materia.carrera_id != alumno.carrera_id:
                raise ErrorInscripcion(
                    f'La materia {materia.nombre} no pertenece a la carrera '
                    f'de {alumno.matricula}.'
                )
            if alumno.ha_cursado(materia):
                raise ErrorInscripcion(
                    f'{alumno.matricula} ya cursó la materia {materia.nombre}.'
                )
            if Calificacion.objects.filter(alumno=alumno, grupo=bloqueado).exists():
                raise ErrorInscripcion(
                    f'{alumno.matricula} ya está inscrito en ese grupo.'
                )
            if bloqueado.esta_lleno:
                raise ErrorInscripcion(
                    f'El grupo de {materia.nombre} ({bloqueado.horario}) ya '
                    f'llenó su cupo de {bloqueado.cupo} lugares.'
                )

            inscripcion = Calificacion.objects.create(
                alumno=alumno, grupo=bloqueado)
            # Una fila de calificación por cada unidad de la materia, lista
            # para que la coordinación solo tenga que capturar el valor.
            CalificacionUnidad.objects.bulk_create([
                CalificacionUnidad(calificacion=inscripcion, numero_unidad=numero)
                for numero in range(1, materia.unidades + 1)
            ])
            creadas.append(inscripcion)
            Grupo.objects.filter(pk=bloqueado.pk).update(
                num_alumnos=F('num_alumnos') + 1)

    return creadas


def desinscribir_alumno(alumno, calificaciones):
    """Da de baja inscripciones del alumno y libera los lugares del grupo."""
    calificaciones = list(calificaciones)
    if not calificaciones:
        return 0

    with transaction.atomic():
        for calificacion in calificaciones:
            grupo_id = calificacion.grupo_id
            calificacion.delete()
            Grupo.objects.filter(pk=grupo_id, num_alumnos__gt=0).update(
                num_alumnos=F('num_alumnos') - 1)
    return len(calificaciones)