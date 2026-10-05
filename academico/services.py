"""Reglas de negocio de la inscripción de alumnos a grupos."""

from django.db import transaction
from django.db.models import F

from .models import Calificacion, Grupo, Periodo


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
            f'{alumno.matricula} ya tiene una carga académica activa en el '
            f'periodo {periodo}.'
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

            creadas.append(Calificacion.objects.create(
                alumno=alumno, grupo=bloqueado))
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