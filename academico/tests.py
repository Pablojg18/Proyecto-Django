"""Pruebas de roles, permisos e inscripción del sistema escolar."""

from datetime import time
from decimal import Decimal
from io import StringIO

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .forms import GrupoForm
from .models import (Alumno, Calificacion, CalificacionUnidad, Carrera,
                     Grupo, Materia, Perfil, Periodo)
from .services import ErrorInscripcion, desinscribir_alumno, inscribir_alumno

PERIODO = settings.PERIODO_ACTUAL
PERIODO_ANTERIOR = '2025-2'


class BaseSistema(TestCase):
    """Datos mínimos: dos carreras, dos alumnos y tres grupos."""

    @classmethod
    def setUpTestData(cls):
        cls.periodo, _ = Periodo.objects.get_or_create(
            nombre=PERIODO, defaults={'activo': True})
        cls.periodo.activar()
        cls.periodo_anterior = Periodo.objects.create(
            nombre=PERIODO_ANTERIOR, activo=False)

        cls.carrera = Carrera.objects.create(
            codigo='ISC', nombre='Ingeniería en Sistemas', duracion=8,
            creditos=300)
        cls.otra_carrera = Carrera.objects.create(
            codigo='CONT', nombre='Contaduría', duracion=8, creditos=350)

        cls.materia_1 = Materia.objects.create(
            codigo='MAT101', nombre='Matemáticas I', unidades=4, creditos=5,
            carrera=cls.carrera)
        cls.materia_2 = Materia.objects.create(
            codigo='MAT102', nombre='Matemáticas II', unidades=4, creditos=5,
            carrera=cls.carrera)
        cls.materia_ajena = Materia.objects.create(
            codigo='CON101', nombre='Contabilidad I', unidades=4, creditos=5,
            carrera=cls.otra_carrera)

        cls.grupo_1 = Grupo.objects.create(
            materia=cls.materia_1, periodo=cls.periodo, cupo=30, num_alumnos=0,
            hora_inicio=time(8, 0), hora_fin=time(9, 30), aula='A-101')
        cls.grupo_2 = Grupo.objects.create(
            materia=cls.materia_2, periodo=cls.periodo, cupo=1, num_alumnos=0,
            hora_inicio=time(10, 0), hora_fin=time(11, 30), aula='B-204')
        cls.grupo_ajeno = Grupo.objects.create(
            materia=cls.materia_ajena, periodo=cls.periodo, cupo=30,
            num_alumnos=0, hora_inicio=time(12, 0), hora_fin=time(13, 30),
            aula='C-101')

        cls.alumno = Alumno.objects.create(
            matricula='20260001', nombre='Ana López', semestre=2,
            carrera=cls.carrera)
        cls.otro_alumno = Alumno.objects.create(
            matricula='20260002', nombre='Luis Pérez', semestre=1,
            carrera=cls.carrera)

        cls.admin = cls.crear_usuario('jefe', 'ADMINISTRADOR')
        cls.coordinador = cls.crear_usuario('coordi', 'COORDINADOR')
        cls.estudiante = cls.crear_usuario('20260001', 'ESTUDIANTE',
                                           alumno=cls.alumno)
        cls.otro_estudiante = cls.crear_usuario('20260002', 'ESTUDIANTE',
                                                alumno=cls.otro_alumno)

    @staticmethod
    def crear_usuario(username, rol, alumno=None):
        usuario = User.objects.create_user(
            username=username, password='clave-de-prueba', first_name=username)
        Perfil.objects.create(usuario=usuario, rol=rol, alumno=alumno)
        return usuario

    @staticmethod
    def calificar(alumno, grupo, valores=None):
        """Inscribe al alumno y califica sus unidades.

        ``valores`` es una lista con la calificación de cada unidad; si se
        omite, las unidades quedan sin calificar.
        """
        inscripcion = Calificacion.objects.create(alumno=alumno, grupo=grupo)
        valores = list(valores or [])
        CalificacionUnidad.objects.bulk_create([
            CalificacionUnidad(
                calificacion=inscripcion, numero_unidad=numero + 1,
                valor=valores[numero] if numero < len(valores) else None)
            for numero in range(grupo.materia.unidades)
        ])
        return inscripcion

    def calificar_todas_las_unidades(self, alumno, grupo, valor):
        """Califica todas las unidades de la materia con el mismo valor."""
        return self.calificar(alumno, grupo,
                              [Decimal(valor)] * grupo.materia.unidades)


class PruebasSesion(BaseSistema):
    def test_inicio_y_cierre_de_sesion(self):
        respuesta = self.client.post(
            reverse('login'),
            {'username': 'coordi', 'password': 'clave-de-prueba'},
        )
        self.assertRedirects(respuesta, reverse('index'))
        self.assertTrue(self.client.session.get('_auth_user_id'))

        respuesta = self.client.post(reverse('logout'))
        self.assertRedirects(respuesta, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_sin_sesion_toda_operacion_exige_login(self):
        for url in ['index', 'alumno_list', 'grupo_list', 'periodo_list',
                    'usuario_list', 'mi_inscripcion', 'mi_carga_academica',
                    'mi_cardex', 'usuario_create_alumno', 'carrera_create']:
            with self.subTest(url=url):
                respuesta = self.client.get(reverse(url))
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse('login'), respuesta.url)

    def test_password_incorrecto_no_entra(self):
        respuesta = self.client.post(
            reverse('login'), {'username': 'coordi', 'password': 'mala'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)


class PruebasPermisosPorRol(BaseSistema):
    def obtener(self, url, **kwargs):
        return self.client.get(url, kwargs)

    def test_administrador_administra_los_catalogos(self):
        self.client.force_login(self.admin)
        for url in ['alumno_list', 'carrera_list', 'carrera_create',
                    'materia_list', 'materia_create', 'grupo_list',
                    'grupo_create', 'periodo_list', 'periodo_create',
                    'usuario_list', 'usuario_create', 'usuario_create_alumno',
                    'usuario_create_personal', 'inscripcion_alumnos']:
            with self.subTest(url=url):
                respuesta = self.obtener(reverse(url))
                self.assertEqual(respuesta.status_code, 200)

    def test_administrador_todas_las_funciones_son_suyas(self):
        """El administrador también captura calificaciones y consulta cargas."""
        self.client.force_login(self.admin)
        url = reverse('alumno_cardex', args=[self.alumno.matricula])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse('carga_de_alumno', args=[self.alumno.matricula])
            ).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse('inscripcion_alumno', args=[self.alumno.matricula])
            ).status_code, 200)

    def test_alta_de_alumno_desde_catalogos_va_a_usuarios(self):
        """`/alumnos/nuevo/` ya no da de alta: lleva a la pantalla de usuarios."""
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('alumno_create'))
        self.assertRedirects(respuesta, reverse('usuario_create_alumno'))

    def test_coordinador_gestiona_alumnos_desde_usuarios(self):
        """El coordinador da de alta y edita alumnos, pero no catálogos."""
        self.client.force_login(self.coordinador)
        for url in ['grupo_list', 'grupo_create', 'periodo_list',
                    'periodo_create', 'inscripcion_alumnos', 'usuario_list',
                    'usuario_create', 'usuario_create_alumno', 'alumno_list']:
            with self.subTest(url=url):
                self.assertEqual(self.obtener(reverse(url)).status_code, 200)

        self.assertRedirects(
            self.obtener(reverse('alumno_create')),
            reverse('usuario_create_alumno'))

        # La edición del alumno vive en Usuarios, no en el catálogo.
        for url in ['carrera_create', 'materia_create']:
            with self.subTest(url=url):
                respuesta = self.obtener(reverse(url))
                self.assertRedirects(respuesta, reverse('index'))

        respuesta = self.obtener(
            reverse('alumno_update', args=[self.alumno.matricula]))
        self.assertRedirects(respuesta, reverse('index'))

    def test_estudiante_solo_accede_a_sus_operaciones(self):
        self.client.force_login(self.estudiante)
        for url in ['mi_inscripcion', 'mi_carga_academica', 'mi_cardex']:
            with self.subTest(url=url):
                self.assertEqual(self.obtener(reverse(url)).status_code, 200)

        for url in ['alumno_list', 'carrera_list', 'materia_list',
                    'grupo_list', 'grupo_create', 'alumno_create',
                    'usuario_list', 'usuario_create', 'periodo_list',
                    'inscripcion_alumnos', 'carrera_create', 'materia_create']:
            with self.subTest(url=url):
                respuesta = self.obtener(reverse(url))
                self.assertRedirects(respuesta, reverse('index'))

    def test_estudiante_no_modifica_calificaciones(self):
        self.client.force_login(self.estudiante)
        url = reverse('alumno_cardex', args=[self.alumno.matricula])
        self.assertRedirects(self.client.get(url), reverse('index'))

    def test_mi_cardex_del_estudiante_es_solo_lectura(self):
        self.calificar_todas_las_unidades(self.alumno, self.grupo_1, '90')
        self.client.force_login(self.estudiante)
        respuesta = self.client.get(reverse('mi_cardex'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context['solo_lectura'])
        self.assertNotContains(respuesta, 'Guardar calificaciones')
        self.assertContains(respuesta, 'Matemáticas I')
        self.assertContains(respuesta, 'Aprobada')

    def test_administracion_modifica_calificaciones(self):
        for usuario in (self.admin, self.coordinador):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                url = reverse('alumno_cardex', args=[self.alumno.matricula])
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_usuario_sin_rol_no_accede_a_operaciones(self):
        usuario = User.objects.create_user(username='sinerol', password='x')
        self.client.force_login(usuario)
        for url in ['alumno_list', 'mi_inscripcion', 'mi_carga_academica']:
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(reverse(url)),
                                     reverse('index'))

    def test_superusuario_ignora_la_matriz_de_roles(self):
        superusuario = User.objects.create_superuser(
            username='super', password='clave', email='s@e.com')
        self.client.force_login(superusuario)
        for url in ['grupo_list', 'inscripcion_alumnos', 'usuario_list',
                    'periodo_list', 'alumno_list']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(reverse(url)).status_code, 200)

    def test_superusuario_sin_alumno_asociado_no_entra_al_portal_estudiante(self):
        superusuario = User.objects.create_superuser(
            username='super2', password='clave', email='s2@e.com')
        self.client.force_login(superusuario)
        respuesta = self.client.get(reverse('mi_carga_academica'))
        self.assertRedirects(respuesta, reverse('index'))


class PruebasCruds(BaseSistema):
    def test_alta_de_alumno_crea_su_usuario_con_rol_estudiante(self):
        self.client.force_login(self.admin)
        datos = {
            'matricula': '20260009', 'nombre': 'Rita Sánchez',
            'carrera': self.carrera.pk, 'semestre': 1,
            'especialidad': '', 'estatus': 'ACTIVO',
            'password_inicial': 'alumno123',
        }
        respuesta = self.client.post(reverse('usuario_create_alumno'), datos)
        self.assertRedirects(respuesta, reverse('usuario_list'))

        alumno = Alumno.objects.get(matricula='20260009')
        perfil = Perfil.objects.get(usuario__username='20260009')
        self.assertEqual(perfil.rol, 'ESTUDIANTE')
        self.assertEqual(perfil.alumno_id, alumno.pk)
        self.assertTrue(
            self.client.login(username='20260009', password='alumno123'))

    def test_alta_de_alumno_exige_contrasena_inicial(self):
        self.client.force_login(self.admin)
        datos = {
            'matricula': '20260010', 'nombre': 'Sin clave',
            'carrera': self.carrera.pk, 'semestre': 1, 'estatus': 'ACTIVO',
        }
        respuesta = self.client.post(reverse('usuario_create_alumno'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Alumno.objects.filter(matricula='20260010').exists())

    def test_alta_edicion_y_baja_de_carrera(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('carrera_create'),
                         {'codigo': 'ADM', 'nombre': 'Administración',
                          'duracion': 8, 'creditos': 300})
        self.assertTrue(Carrera.objects.filter(codigo='ADM').exists())

        self.client.post(reverse('carrera_update', args=['ADM']),
                         {'codigo': 'ADM', 'nombre': 'Administración de Empresas',
                          'duracion': 8, 'creditos': 320})
        carrera = Carrera.objects.get(codigo='ADM')
        self.assertEqual(carrera.nombre, 'Administración de Empresas')
        self.assertEqual(carrera.creditos, 320)

        self.client.post(reverse('carrera_delete', args=['ADM']))
        self.assertFalse(Carrera.objects.filter(codigo='ADM').exists())

    def test_alta_y_baja_de_materia(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('materia_create'),
                         {'codigo': 'MAT103', 'nombre': 'Matemáticas III',
                          'carrera': self.carrera.pk, 'unidades': 4,
                          'creditos': 5})
        self.assertTrue(Materia.objects.filter(codigo='MAT103').exists())
        self.client.post(reverse('materia_delete', args=['MAT103']))
        self.assertFalse(Materia.objects.filter(codigo='MAT103').exists())

    def test_coordinador_alta_grupo_con_materia_del_periodo(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.post(reverse('grupo_create'), {
            'materia': self.materia_1.pk, 'periodo': self.periodo.pk,
            'hora_inicio': '07:00', 'hora_fin': '08:30', 'aula': 'A-102',
            'cupo': 25, 'num_alumnos': 0,
        })
        self.assertRedirects(respuesta, reverse('grupo_list'))
        grupo = Grupo.objects.get(hora_inicio=time(7, 0), aula='A-102')
        self.assertEqual(grupo.periodo_id, self.periodo.pk)
        self.assertEqual(grupo.horario, '07:00 - 08:30')
        self.assertEqual(grupo.turno_display, 'Matutino')

    def test_alta_de_grupo_preselecciona_el_periodo_vigente(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.get(reverse('grupo_create'))
        self.assertEqual(respuesta.context['form'].initial['periodo'],
                         self.periodo.pk)

    def test_alta_de_periodo_desde_el_catalogo(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.post(reverse('periodo_create'),
                                     {'nombre': '2026-2', 'activo': 'on'})
        self.assertRedirects(respuesta, reverse('periodo_list'))
        nuevo = Periodo.objects.get(nombre='2026-2')
        self.assertTrue(nuevo.activo)
        self.periodo.refresh_from_db()
        self.assertFalse(self.periodo.activo)
        self.assertEqual(Periodo.actual().pk, nuevo.pk)

    def test_baja_de_alumno_borra_su_usuario(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('alumno_delete', args=[self.otro_alumno.pk]))
        self.assertFalse(Alumno.objects.filter(pk=self.otro_alumno.pk).exists())
        self.assertFalse(
            User.objects.filter(username=self.otro_alumno.matricula).exists())

    def test_pantallas_de_confirmacion_de_baja(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(reverse('alumno_delete',
                                    args=[self.alumno.pk])).status_code, 200)
        self.client.force_login(self.coordinador)
        self.assertEqual(
            self.client.get(reverse('grupo_delete',
                                    args=[self.grupo_1.pk])).status_code, 200)
        self.assertEqual(
            self.client.get(reverse('grupo_update',
                                    args=[self.grupo_1.pk])).status_code, 200)

    def test_no_se_reutiliza_la_matricula_de_un_usuario_existente(self):
        self.client.force_login(self.admin)
        datos = {
            'matricula': self.otro_alumno.matricula, 'nombre': 'Duplicado',
            'carrera': self.carrera.pk, 'semestre': 1,
            'estatus': 'ACTIVO', 'password_inicial': 'alumno123',
        }
        respuesta = self.client.post(reverse('usuario_create_alumno'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ya existe un usuario con esta matrícula')

    def test_editar_alumno_no_pide_contrasena_nueva(self):
        self.client.force_login(self.admin)
        datos = {
            'matricula': self.alumno.matricula, 'nombre': 'Ana López Ramírez',
            'carrera': self.carrera.pk, 'semestre': 3,
            'especialidad': 'Sistemas', 'estatus': 'ACTIVO',
        }
        respuesta = self.client.post(
            reverse('alumno_update', args=[self.alumno.pk]), datos)
        self.assertRedirects(respuesta, reverse('alumno_list'))
        self.alumno.refresh_from_db()
        self.assertEqual(self.alumno.semestre, 3)
        self.assertTrue(self.client.login(username='20260001',
                                          password='clave-de-prueba'))

    def test_el_formulario_de_edicion_no_muestra_contrasena_inicial(self):
        """La contraseña se administra desde Usuarios, no desde el catálogo."""
        self.client.force_login(self.admin)
        respuesta = self.client.get(
            reverse('alumno_update', args=[self.alumno.pk]))

        self.assertNotIn('password_inicial', respuesta.context['form'].fields)
        self.assertNotContains(respuesta, 'Contraseña inicial')

    def test_el_alta_sigue_pidiendo_contrasena_inicial(self):
        """El alta de alumno (desde Usuarios) sí necesita la contraseña inicial."""
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('usuario_create_alumno'))

        self.assertIn('password_inicial', respuesta.context['form'].fields)
        self.assertContains(respuesta, 'Contraseña inicial')


class PruebasInscripcion(BaseSistema):
    def test_coordinador_filtra_alumnos_para_inscribir(self):
        self.client.force_login(self.coordinador)
        url = reverse('inscripcion_alumnos')
        self.assertEqual(self.client.get(url, {'q': '20260002'}).status_code, 200)
        contenido = self.client.get(url, {'q': '20260002'}).context['alumnos']
        self.assertEqual([a.matricula for a in contenido], ['20260002'])

        contenido = self.client.get(
            url, {'carrera': self.otra_carrera.pk}).context['alumnos']
        self.assertEqual(list(contenido), [])

    def test_coordinador_inscribe_alumno_y_ocupa_lugar(self):
        self.client.force_login(self.coordinador)
        url = reverse('inscripcion_alumno', args=[self.alumno.matricula])
        respuesta = self.client.post(url, {'grupos': [self.grupo_1.pk]})

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(
            Calificacion.objects.filter(alumno=self.alumno,
                                        grupo=self.grupo_1).exists())
        self.grupo_1.refresh_from_db()
        self.assertEqual(self.grupo_1.num_alumnos, 1)

    def test_estudiante_se_inscribe_en_sus_materias(self):
        self.client.force_login(self.estudiante)
        respuesta = self.client.post(reverse('mi_inscripcion'),
                                     {'grupos': [self.grupo_1.pk]})
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(
            Calificacion.objects.filter(alumno=self.alumno,
                                        grupo=self.grupo_1).exists())

    def test_no_se_puede_inscribir_dos_veces_en_el_periodo(self):
        """El estudiante solo se inscribe una vez por periodo."""
        Calificacion.objects.create(alumno=self.alumno, grupo=self.grupo_1)
        self.grupo_1.num_alumnos = 1
        self.grupo_1.save(update_fields=['num_alumnos'])

        self.client.force_login(self.estudiante)
        respuesta = self.client.post(reverse('mi_inscripcion'),
                                     {'grupos': [self.grupo_2.pk]},
                                     follow=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'una vez por periodo')
        self.assertFalse(
            Calificacion.objects.filter(alumno=self.alumno,
                                        grupo=self.grupo_2).exists())

    def test_el_servicio_tambien_bloquea_la_segunda_inscripcion(self):
        Calificacion.objects.create(alumno=self.alumno, grupo=self.grupo_1)

        with self.assertRaisesMessage(ErrorInscripcion, 'ya se inscribió'):
            inscribir_alumno(self.alumno, [self.grupo_2])

    def test_el_estudiante_elige_todas_sus_materias_de_una_vez(self):
        self.client.force_login(self.estudiante)
        respuesta = self.client.post(
            reverse('mi_inscripcion'),
            {'grupos': [self.grupo_1.pk, self.grupo_2.pk]})

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            Calificacion.objects.filter(alumno=self.alumno).count(), 2)

    def test_coordinador_sigue_pudiendo_inscribir_con_carga_activa(self):
        Calificacion.objects.create(alumno=self.alumno, grupo=self.grupo_1)
        self.client.force_login(self.coordinador)
        respuesta = self.client.post(
            reverse('inscripcion_alumno', args=[self.alumno.matricula]),
            {'grupos': [self.grupo_2.pk]})
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(
            Calificacion.objects.filter(alumno=self.alumno,
                                        grupo=self.grupo_2).exists())

    def test_no_se_puede_inscribir_en_materia_ya_cursada(self):
        cursada = self.calificar_todas_las_unidades(
            self.alumno, self.grupo_1, '85')
        cursada.grupo.num_alumnos = 1
        cursada.grupo.save(update_fields=['num_alumnos'])

        with self.assertRaisesMessage(ErrorInscripcion, 'ya cursó'):
            inscribir_alumno(self.alumno, [self.grupo_1], forzar=True)

    def test_no_se_puede_inscribir_en_materia_de_otra_carrera(self):
        with self.assertRaisesMessage(ErrorInscripcion, 'no pertenece'):
            inscribir_alumno(self.alumno, [self.grupo_ajeno])

    def test_no_se_puede_inscribir_en_grupo_lleno(self):
        Grupo.objects.filter(pk=self.grupo_2.pk).update(num_alumnos=1)
        with self.assertRaisesMessage(ErrorInscripcion, 'llenó su cupo'):
            inscribir_alumno(self.alumno, [self.grupo_2])

    def test_no_se_puede_inscribir_en_grupo_de_otro_periodo(self):
        grupo_antiguo = Grupo.objects.create(
            materia=self.materia_1, periodo=self.periodo_anterior, cupo=10,
            num_alumnos=0, hora_inicio=time(9, 0), hora_fin=time(10, 30))
        with self.assertRaisesMessage(ErrorInscripcion, 'inscripción está abierta'):
            inscribir_alumno(self.alumno, [grupo_antiguo])

    def test_al_cambiar_el_periodo_vigente_se_abre_la_inscripcion(self):
        """Alumno con carga en 2026-1 puede inscribirse en el nuevo periodo."""
        self.calificar_todas_las_unidades(self.alumno, self.grupo_1, '80')
        Grupo.objects.filter(pk=self.grupo_1.pk).update(num_alumnos=1)

        siguiente = Periodo.objects.create(nombre='2026-2', activo=False)
        materia_nueva = Materia.objects.create(
            codigo='MAT103', nombre='Matemáticas III', unidades=4,
            creditos=5, carrera=self.carrera)
        grupo_nuevo = Grupo.objects.create(
            materia=materia_nueva, periodo=siguiente, cupo=10, num_alumnos=0,
            hora_inicio=time(8, 0), hora_fin=time(9, 30), aula='A-101')

        Periodo.objects.get(pk=siguiente.pk).activar()

        inscribir_alumno(self.alumno, [grupo_nuevo])
        self.assertTrue(
            Calificacion.objects.filter(alumno=self.alumno,
                                        grupo=grupo_nuevo).exists())

    def test_la_inscripcion_es_atomica(self):
        """Si un grupo falla, ninguno de los seleccionados se inscribe."""
        Grupo.objects.filter(pk=self.grupo_2.pk).update(num_alumnos=1)
        with self.assertRaises(ErrorInscripcion):
            inscribir_alumno(self.alumno, [self.grupo_1, self.grupo_2])
        self.assertEqual(Calificacion.objects.count(), 0)
        self.grupo_1.refresh_from_db()
        self.assertEqual(self.grupo_1.num_alumnos, 0)

    def test_coordinador_da_de_baja_inscripcion_y_libera_lugar(self):
        calificacion = Calificacion.objects.create(
            alumno=self.alumno, grupo=self.grupo_1)
        Grupo.objects.filter(pk=self.grupo_1.pk).update(num_alumnos=1)

        self.client.force_login(self.coordinador)
        url = reverse('inscripcion_alumno', args=[self.alumno.matricula])
        respuesta = self.client.post(url, {
            'accion': 'quitar', 'quitar': [calificacion.pk]})

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(
            Calificacion.objects.filter(pk=calificacion.pk).exists())
        self.grupo_1.refresh_from_db()
        self.assertEqual(self.grupo_1.num_alumnos, 0)

    def test_el_estudiante_no_puede_darse_de_baja(self):
        calificacion = Calificacion.objects.create(
            alumno=self.alumno, grupo=self.grupo_1)
        self.client.force_login(self.estudiante)
        respuesta = self.client.post(reverse('mi_inscripcion'), {
            'accion': 'quitar', 'quitar': [calificacion.pk]}, follow=True)

        self.assertContains(respuesta, 'Solo tu coordinador')
        self.assertTrue(
            Calificacion.objects.filter(pk=calificacion.pk).exists())

    def test_las_materias_no_disponibles_no_se_muestran(self):
        """Solo se listan las materias que el alumno sí puede tomar."""
        cursada = Calificacion.objects.create(
            alumno=self.alumno, grupo=self.grupo_1)
        cursada.grupo.num_alumnos = 1
        cursada.grupo.save(update_fields=['num_alumnos'])
        Grupo.objects.filter(pk=self.grupo_2.pk).update(num_alumnos=1)

        self.client.force_login(self.estudiante)
        respuesta = self.client.get(reverse('mi_inscripcion'))

        self.assertNotContains(respuesta, 'Materia ya cursada')
        self.assertNotContains(respuesta, 'Grupo sin cupo')
        self.assertNotContains(respuesta, 'Materias no disponibles')
        self.assertContains(respuesta, 'No hay materias disponibles')

    def test_el_alumno_solo_ve_su_propia_carga_academica(self):
        """El estudiante no cae en la vista restringida de la coordinación."""
        self.client.force_login(self.estudiante)
        respuesta = self.client.get(reverse('mi_inscripcion'))

        self.assertContains(respuesta, reverse('mi_carga_academica'))
        self.assertNotContains(respuesta, reverse('carga_de_alumno',
                                                  args=[self.alumno.matricula]))

    def test_desinscribir_no_deja_num_alumnos_negativo(self):
        calificacion = Calificacion.objects.create(
            alumno=self.alumno, grupo=self.grupo_1)
        desinscribir_alumno(self.alumno, [calificacion])
        self.grupo_1.refresh_from_db()
        self.assertEqual(self.grupo_1.num_alumnos, 0)


class PruebasChoqueDeHorarios(BaseSistema):
    """Un alumno no puede tomar dos grupos que se impartan a la misma hora."""

    def setUp(self):
        self.materia_3 = Materia.objects.create(
            codigo='MAT103', nombre='Matemáticas III', unidades=4,
            creditos=5, carrera=self.carrera)
        # Mismo horario que grupo_1: choca de frente.
        self.grupo_choque = Grupo.objects.create(
            materia=self.materia_3, periodo=self.periodo, cupo=10,
            num_alumnos=0, hora_inicio=time(8, 30), hora_fin=time(10, 0),
            aula='A-202')
        # Se traslapa un poco con grupo_1.
        self.grupo_traslape = Grupo.objects.create(
            materia=self.materia_3, periodo=self.periodo, cupo=10,
            num_alumnos=0, hora_inicio=time(9, 0), hora_fin=time(10, 0),
            aula='A-203')

    def test_el_horario_se_calcula_desde_las_horas(self):
        self.assertEqual(self.grupo_1.horario, '08:00 - 09:30')
        self.assertEqual(self.grupo_1.turno_display, 'Matutino')
        evening = Grupo.objects.create(
            materia=self.materia_3, periodo=self.periodo, cupo=10,
            hora_inicio=time(18, 0), hora_fin=time(19, 30), aula='A-204')
        self.assertEqual(evening.turno_display, 'Vespertino')

    def test_se_detecta_el_choque_entre_grupos(self):
        self.assertTrue(self.grupo_1.se_choca_con(self.grupo_choque))
        self.assertTrue(self.grupo_1.se_choca_con(self.grupo_traslape))
        self.assertFalse(self.grupo_1.se_choca_con(self.grupo_2))

    def test_el_servicio_rechaza_dos_materias_a_la_misma_hora(self):
        with self.assertRaisesMessage(ErrorInscripcion, 'misma hora'):
            inscribir_alumno(self.alumno, [self.grupo_1, self.grupo_choque])
        self.assertEqual(Calificacion.objects.count(), 0)

    def test_el_formulario_rechaza_dos_materias_a_la_misma_hora(self):
        from .forms import InscripcionForm, grupos_inscribibles

        opciones = grupos_inscribibles(self.alumno, self.periodo)
        form = InscripcionForm(
            {'grupos': [self.grupo_1.pk, self.grupo_choque.pk]},
            opciones=opciones, alumno=self.alumno)

        self.assertFalse(form.is_valid())
        self.assertIn('misma hora', str(form.errors))

    def test_no_se_puede_agregar_a_lo_que_ya_se_tiene(self):
        """El coordinador tampoco cruza una materia nueva con la ya inscrita."""
        Calificacion.objects.create(alumno=self.alumno, grupo=self.grupo_1)
        Grupo.objects.filter(pk=self.grupo_1.pk).update(num_alumnos=1)

        with self.assertRaisesMessage(ErrorInscripcion, 'choca con'):
            inscribir_alumno(self.alumno, [self.grupo_choque], forzar=True)

    def test_la_materia_que_choca_no_se_ofrece_en_la_pantalla(self):
        Calificacion.objects.create(alumno=self.alumno, grupo=self.grupo_1)
        Grupo.objects.filter(pk=self.grupo_1.pk).update(num_alumnos=1)

        self.client.force_login(self.coordinador)
        respuesta = self.client.get(
            reverse('inscripcion_alumno', args=[self.alumno.matricula]))

        ofrecidos = [str(grupo) for grupo in respuesta.context['form'].fields[
            'grupos'].queryset]
        self.assertNotIn(str(self.grupo_choque), ofrecidos)
        self.assertNotIn(str(self.grupo_traslape), ofrecidos)
        self.assertIn(str(self.grupo_2), ofrecidos)


class PruebasHorariosDeGrupo(BaseSistema):
    def test_el_horario_va_de_07_a_20(self):
        valido = GrupoForm({
            'materia': self.materia_1.pk, 'periodo': self.periodo.pk,
            'hora_inicio': '07:00', 'hora_fin': '20:00', 'aula': 'A-9',
            'cupo': 10, 'num_alumnos': 0,
        })
        self.assertTrue(valido.is_valid(), valido.errors)

        for inicio, fin in [('06:59', '20:00'), ('07:00', '20:01'),
                            ('21:00', '22:00')]:
            with self.subTest(inicio=inicio, fin=fin):
                form = GrupoForm({
                    'materia': self.materia_1.pk, 'periodo': self.periodo.pk,
                    'hora_inicio': inicio, 'hora_fin': fin, 'aula': 'A-9',
                    'cupo': 10, 'num_alumnos': 0,
                })
                self.assertFalse(form.is_valid())

    def test_la_hora_final_debe_ser_posterior(self):
        form = GrupoForm({
            'materia': self.materia_1.pk, 'periodo': self.periodo.pk,
            'hora_inicio': '10:00', 'hora_fin': '09:00', 'aula': 'A-9',
            'cupo': 10, 'num_alumnos': 0,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('hora_fin', form.errors)

    def test_el_modelo_tambien_valida_el_rango(self):
        grupo = Grupo(materia=self.materia_1, periodo=self.periodo, cupo=10,
                      hora_inicio=time(6, 0), hora_fin=time(7, 0), aula='A-9')
        with self.assertRaises(ValidationError):
            grupo.full_clean()

    def test_el_grupo_no_admite_mas_alumnos_que_cupo(self):
        grupo = Grupo(materia=self.materia_1, periodo=self.periodo, cupo=5,
                      num_alumnos=6, hora_inicio=time(7, 0),
                      hora_fin=time(8, 30), aula='A-9')
        with self.assertRaises(ValidationError):
            grupo.full_clean()


class PruebasFiltroDeAlumnos(BaseSistema):
    def setUp(self):
        Alumno.objects.create(matricula='20260003', nombre='Rita Sánchez',
                               semestre=3, estatus='BAJA_TEMP',
                               carrera=self.otra_carrera)

    def alumnos_de(self, **consulta):
        self.client.force_login(self.coordinador)
        respuesta = self.client.get(reverse('alumno_list'), consulta)
        self.assertEqual(respuesta.status_code, 200)
        return [a.matricula for a in respuesta.context['alumnos']]

    def test_sin_filtro_muestra_todos(self):
        self.assertEqual(self.alumnos_de(),
                         ['20260001', '20260002', '20260003'])

    def test_filtra_por_matricula_nombre_o_carrera(self):
        self.assertEqual(self.alumnos_de(q='20260002'), ['20260002'])
        self.assertEqual(self.alumnos_de(q='Rita'), ['20260003'])
        self.assertEqual(self.alumnos_de(q='Sistemas'), ['20260001',
                                                         '20260002'])
        self.assertEqual(self.alumnos_de(q='Contaduría'), ['20260003'])
        self.assertEqual(self.alumnos_de(q='zzzz'), [])

    def test_filtra_por_carrera_estatus_y_semestre(self):
        self.assertEqual(self.alumnos_de(carrera=self.otra_carrera.pk),
                         ['20260003'])
        self.assertEqual(self.alumnos_de(estatus='BAJA_TEMP'), ['20260003'])
        self.assertEqual(self.alumnos_de(semestre=3), ['20260003'])
        self.assertEqual(self.alumnos_de(semestre=9), [])

    def test_combina_filtros(self):
        self.assertEqual(
            self.alumnos_de(carrera=self.otra_carrera.pk, estatus='ACTIVO'),
            [])

    def test_el_filtro_marca_los_campos_del_formulario(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.get(reverse('alumno_list'),
                                    {'q': 'Rita', 'semestre': '3'})

        filtro = respuesta.context['filtro']
        self.assertEqual(filtro.cleaned_data['q'], 'Rita')
        self.assertEqual(filtro.cleaned_data['semestre'], 3)
        self.assertTrue(respuesta.context['filtro_activo'])
        self.assertContains(respuesta, 'Limpiar')


class PruebasFiltroDeGrupos(BaseSistema):
    def setUp(self):
        self.grupo_anterior = Grupo.objects.create(
            materia=self.materia_2, periodo=self.periodo_anterior, cupo=10,
            num_alumnos=0, hora_inicio=time(15, 0), hora_fin=time(16, 30),
            aula='D-1')

    def grupos_de(self, **consulta):
        self.client.force_login(self.coordinador)
        respuesta = self.client.get(reverse('grupo_list'), consulta)
        self.assertEqual(respuesta.status_code, 200)
        return list(respuesta.context['grupos'])

    def test_sin_filtro_muestra_el_periodo_vigente(self):
        self.assertEqual(self.grupos_de(),
                         [self.grupo_ajeno, self.grupo_1, self.grupo_2])
        self.assertNotIn(self.grupo_anterior, Grupo.objects.filter(
            periodo=self.periodo))

    def test_al_elegir_un_periodo_solo_ve_sus_grupos(self):
        grupos = self.grupos_de(periodo=self.periodo_anterior.pk)

        self.assertEqual(grupos, [self.grupo_anterior])
        self.assertNotIn(self.grupo_1, grupos)

    def test_el_periodo_elegido_queda_marcado(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.get(
            reverse('grupo_list'), {'periodo': self.periodo_anterior.pk})

        self.assertEqual(respuesta.context['periodo_seleccionado'],
                         self.periodo_anterior)

    def test_un_periodo_inexistente_cae_en_el_vigente(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.get(reverse('grupo_list'), {'periodo': 999})

        self.assertEqual(respuesta.context['periodo_seleccionado'],
                         self.periodo)


class PruebasListasVacias(BaseSistema):
    """Una lista sin registros se avisa fuera de la tabla.

    Poner el aviso como fila con `colspan` dentro de `tbody` hace que
    DataTables la lea como una fila de datos de una sola columna y avise de
    columnas desconocidas al abrir un periodo sin grupos.
    """

    LISTADOS = ['grupo_list', 'alumno_list', 'carrera_list', 'materia_list',
                'periodo_list', 'usuario_list']

    def test_ningun_listado_deja_una_fila_colspan(self):
        for nombre in self.LISTADOS:
            with self.subTest(listado=nombre):
                self.client.force_login(self.admin)
                respuesta = self.client.get(reverse(nombre))

                self.assertEqual(respuesta.status_code, 200)
                self.assertNotContains(respuesta, 'colspan=')

    def test_el_periodo_sin_grupos_avisa_sin_tabla(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.get(reverse('grupo_list'),
                                    {'periodo': self.periodo_anterior.pk})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'No hay grupos registrados')
        self.assertNotContains(respuesta, 'tabla-grupos')

    def test_un_filtro_sin_coincidencias_avisa_sin_tabla(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('alumno_list'),
                                    {'q': 'no-existe-esta-matricula'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'No hay alumnos que coincidan')
        self.assertNotContains(respuesta, 'tabla-alumnos')

    def test_con_registros_se_mantiene_la_tabla(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.get(reverse('grupo_list'))

        self.assertContains(respuesta, 'tabla-grupos')
        self.assertContains(respuesta, 'iniciarTabla')
        self.assertNotContains(respuesta, 'class="vacio"')


class PruebasBorradosProtegidos(BaseSistema):
    def test_no_se_borra_una_materia_con_grupos(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse('materia_delete', args=[self.materia_1.codigo]),
            follow=True)

        self.assertRedirects(respuesta, reverse('materia_list'))
        self.assertContains(respuesta, 'tiene grupos abiertos')
        self.assertTrue(Materia.objects.filter(pk=self.materia_1.pk).exists())

    def test_no_se_borra_una_carrera_con_materias(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse('carrera_delete', args=[self.carrera.pk]), follow=True)

        self.assertRedirects(respuesta, reverse('carrera_list'))
        self.assertContains(respuesta, 'tiene materias o alumnos')
        self.assertTrue(Carrera.objects.filter(pk=self.carrera.pk).exists())

    def test_no_se_borra_un_grupo_con_inscripciones(self):
        Calificacion.objects.create(alumno=self.alumno, grupo=self.grupo_1)
        self.client.force_login(self.coordinador)
        respuesta = self.client.post(
            reverse('grupo_delete', args=[self.grupo_1.pk]), follow=True)

        self.assertRedirects(respuesta, reverse('grupo_list'))
        self.assertContains(respuesta, 'alumnos inscritos')
        self.assertTrue(Grupo.objects.filter(pk=self.grupo_1.pk).exists())


class PruebasCargaAcademica(BaseSistema):
    def setUp(self):
        self.calificar_todas_las_unidades(self.alumno, self.grupo_1, '90')
        Calificacion.objects.create(alumno=self.alumno, grupo=self.grupo_2)

    def test_coordinador_consulta_carga_de_cualquier_alumno(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.get(
            reverse('carga_de_alumno', args=[self.alumno.matricula]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Matemáticas I')
        self.assertContains(respuesta, 'Carga académica actual')

    def test_el_historial_solo_aparece_en_el_cardex(self):
        """La carga académica muestra el periodo vigente, no el historial."""
        self.client.force_login(self.coordinador)
        carga = self.client.get(
            reverse('carga_de_alumno', args=[self.alumno.matricula]))

        self.assertNotContains(carga, 'Historial de materias cursadas')
        self.assertEqual(carga.context['materias_cursadas'], 2)

        cardex = self.client.get(
            reverse('alumno_cardex', args=[self.alumno.matricula]))
        self.assertContains(cardex, 'Historial de materias cursadas')

    def test_estudiante_consulta_su_propia_carga(self):
        self.client.force_login(self.estudiante)
        respuesta = self.client.get(reverse('mi_carga_academica'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.alumno.nombre)

    def test_estudiante_no_consulta_carga_de_otro_alumno(self):
        self.client.force_login(self.estudiante)
        respuesta = self.client.get(
            reverse('carga_de_alumno', args=[self.otro_alumno.matricula]))
        self.assertRedirects(respuesta, reverse('index'))

    def test_carga_calcula_creditos_y_promedio(self):
        self.alumno.refresh_from_db()
        self.assertEqual(self.alumno.creditos_en_curso, 10)
        self.assertEqual(self.alumno.creditos_acumulados, 5)
        self.assertEqual(self.alumno.materias_cursadas, 2)
        self.assertEqual(self.alumno.promedio_general, Decimal('90.0'))
        self.assertTrue(self.alumno.tiene_carga_activa)

    def test_la_carga_no_muestra_el_avance_de_la_carrera(self):
        self.client.force_login(self.estudiante)
        respuesta = self.client.get(reverse('mi_carga_academica'))

        self.assertNotContains(respuesta, 'Avance de la carrera')
        self.assertNotContains(respuesta, 'avance_carrera')


class PruebasCalificacionPorUnidad(BaseSistema):
    """La calificación final es el promedio de las unidades de la materia."""

    def test_se_crea_una_unidad_por_cada_unidad_de_la_materia(self):
        inscripcion = Calificacion.objects.create(
            alumno=self.alumno, grupo=self.grupo_1)

        CalificacionUnidad.objects.bulk_create([
            CalificacionUnidad(calificacion=inscripcion, numero_unidad=numero)
            for numero in range(1, self.materia_1.unidades + 1)
        ])

        unidades = list(inscripcion.unidades)
        self.assertEqual(len(unidades), self.materia_1.unidades)
        self.assertEqual([u.numero_unidad for u in unidades], [1, 2, 3, 4])

    def test_el_promedio_es_el_de_las_unidades(self):
        inscripcion = self.calificar(self.alumno, self.grupo_1,
                                     [Decimal('100'), Decimal('90'),
                                      Decimal('80'), Decimal('70')])

        self.assertEqual(inscripcion.valor_promedio, Decimal('85.0'))
        self.assertTrue(inscripcion.unidades_completas)

    def test_solo_cuenta_el_promedio_de_las_unidades_capturadas(self):
        inscripcion = self.calificar(self.alumno, self.grupo_1,
                                     [Decimal('100'), Decimal('60')])

        self.assertEqual(inscripcion.valor_promedio, Decimal('80.0'))
        self.assertFalse(inscripcion.unidades_completas)

    def test_sin_unidades_calificadas_no_hay_calificacion_final(self):
        inscripcion = Calificacion.objects.create(
            alumno=self.alumno, grupo=self.grupo_1)

        self.assertIsNone(inscripcion.valor_promedio)
        self.assertFalse(inscripcion.esta_calificada)
        self.assertFalse(inscripcion.es_aprobada)

    def test_el_rango_de_aprobado_es_de_70_a_100(self):
        inscripcion = Calificacion.objects.create(
            alumno=self.alumno, grupo=self.grupo_1)
        unidades = list(CalificacionUnidad.objects.bulk_create([
            CalificacionUnidad(calificacion=inscripcion, numero_unidad=numero)
            for numero in range(1, self.materia_1.unidades + 1)
        ]))

        def promedio_con(valor):
            for unidad in unidades:
                unidad.valor = Decimal(valor)
                unidad.save(update_fields=['valor'])
            inscripcion.refresh_from_db()
            return inscripcion.valor_promedio

        self.assertEqual(promedio_con('70'), Decimal('70.0'))
        self.assertTrue(inscripcion.es_aprobada)
        self.assertFalse(inscripcion.es_reprobada)

        self.assertEqual(promedio_con('100'), Decimal('100.0'))
        self.assertTrue(inscripcion.es_aprobada)

        self.assertEqual(promedio_con('69.9'), Decimal('69.9'))
        self.assertFalse(inscripcion.es_aprobada)
        self.assertTrue(inscripcion.es_reprobada)

    def test_el_promedio_general_usa_las_calificaciones_finales(self):
        self.calificar_todas_las_unidades(self.alumno, self.grupo_1, '80')
        self.calificar(self.alumno, self.grupo_2,
                       [Decimal('100'), Decimal('100')])

        self.alumno.refresh_from_db()
        # Promedios finales: 80.0 y 100.0 (las unidades 3 y 4 sin calificar).
        self.assertEqual(self.alumno.promedio_general, Decimal('90.0'))

    def test_la_inscripcion_crea_sus_unidades(self):
        inscribir_alumno(self.alumno, [self.grupo_1])

        inscripcion = Calificacion.objects.get(alumno=self.alumno,
                                               grupo=self.grupo_1)
        self.assertEqual(inscripcion.calificaciones_unidad.count(),
                         self.materia_1.unidades)

    def test_no_se_repite_el_numero_de_unidad(self):
        inscripcion = Calificacion.objects.create(
            alumno=self.alumno, grupo=self.grupo_1)
        CalificacionUnidad.objects.create(calificacion=inscripcion,
                                          numero_unidad=1)
        repetida = CalificacionUnidad(calificacion=inscripcion,
                                      numero_unidad=1)
        with self.assertRaises(ValidationError):
            repetida.full_clean()


class PruebasCardex(BaseSistema):
    def setUp(self):
        self.inscripcion = Calificacion.objects.create(
            alumno=self.alumno, grupo=self.grupo_1)
        self.url = reverse('alumno_cardex', args=[self.alumno.matricula])

    def datos_del_formulario(self, valores):
        """Abre el cardex y arma el POST con una calificación por unidad."""
        respuesta = self.client.get(self.url)
        formset = respuesta.context['formset']
        datos = {
            formset.add_prefix('TOTAL_FORMS'): str(formset.total_form_count()),
            formset.add_prefix('INITIAL_FORMS'): str(
                formset.initial_form_count()),
            formset.add_prefix('MIN_NUM_FORMS'): '0',
            formset.add_prefix('MAX_NUM_FORMS'): '1000',
        }
        for indice, form in enumerate(formset.forms):
            prefijo = formset.add_prefix(str(indice))
            datos[f'{prefijo}-id'] = str(form.instance.pk)
            if indice < len(valores):
                datos[f'{prefijo}-valor'] = valores[indice]
        return datos

    def test_el_cardex_crea_las_unidades_de_la_materia(self):
        self.client.force_login(self.coordinador)
        self.client.get(self.url)

        self.assertEqual(
            CalificacionUnidad.objects.filter(calificacion=self.inscripcion)
            .count(), self.materia_1.unidades)

    def test_coordinador_guarda_calificaciones_por_unidad(self):
        self.client.force_login(self.coordinador)
        datos = self.datos_del_formulario(['100', '90', '80', '70'])

        respuesta = self.client.post(self.url, datos)

        self.assertEqual(respuesta.status_code, 302)
        calificacion = Calificacion.objects.get(pk=self.inscripcion.pk)
        self.assertEqual(calificacion.valor_promedio, Decimal('85.0'))
        self.assertTrue(calificacion.es_aprobada)
        self.assertTrue(calificacion.unidades_completas)
        self.assertIsNotNone(calificacion.fecha_captura)

    def test_una_materia_reprobada_no_suma_creditos(self):
        self.calificar_todas_las_unidades(self.alumno, self.grupo_2, '60')
        self.client.force_login(self.coordinador)
        datos = self.datos_del_formulario(['60'] * (self.materia_1.unidades
                                                    + self.materia_2.unidades))

        self.client.post(self.url, datos)

        self.alumno.refresh_from_db()
        self.assertEqual(self.alumno.creditos_acumulados, 0)
        self.assertEqual(len(self.alumno.materias_reprobadas), 2)

    def test_rechaza_calificacion_fuera_de_rango(self):
        self.client.force_login(self.coordinador)
        datos = self.datos_del_formulario(['120', '80', '80', '80'])

        respuesta = self.client.post(self.url, datos)

        self.assertEqual(respuesta.status_code, 200)
        self.inscripcion.refresh_from_db()
        self.assertIsNone(self.inscripcion.valor_promedio)

    def test_el_cardex_muestra_el_historial_de_materias_cursadas(self):
        self.calificar_todas_las_unidades(self.alumno, self.grupo_2, '95')
        self.client.force_login(self.coordinador)

        respuesta = self.client.get(self.url)

        historial = respuesta.context['historial_completado']
        self.assertEqual([c.grupo_id for c in historial], [self.grupo_2.pk])
        self.assertContains(respuesta, 'Historial de materias cursadas')

    def test_la_calificacion_final_se_actualiza_al_abrir_el_cardex(self):
        """Con todas las unidades capturadas, la columna muestra el promedio."""
        self.client.force_login(self.coordinador)
        self.datos_del_formulario(['100', '90', '80', '70'])
        self.client.post(self.url, self.datos_del_formulario(
            ['100', '90', '80', '70']))

        respuesta = self.client.get(self.url)

        fila = respuesta.context['filas_captura'][0]
        self.assertEqual(fila['valor'], Decimal('85.0'))
        self.assertTrue(fila['aprobada'])
        self.assertTrue(fila['completa'])
        self.assertContains(respuesta, '85.0')

    def test_una_unidad_invalida_deja_la_materia_incompleta(self):
        """Si una unidad no pasa la validación, el promedio ignora ese valor."""
        self.client.force_login(self.coordinador)
        datos = self.datos_del_formulario(['120', '80', '80', '80'])

        respuesta = self.client.post(self.url, datos)

        self.assertEqual(respuesta.status_code, 200)
        fila = respuesta.context['filas_captura'][0]
        self.assertEqual(fila['valor'], Decimal('80.0'))
        self.assertTrue(fila['aprobada'])
        self.assertFalse(fila['completa'])

    def test_cambiar_las_unidades_de_la_materia_ajusta_el_cardex(self):
        self.calificar(self.alumno, self.grupo_2, [Decimal('95')])
        self.client.force_login(self.coordinador)

        self.materia_2.unidades = 2
        self.materia_2.save(update_fields=['unidades'])
        self.client.get(self.url)

        inscripcion = Calificacion.objects.get(alumno=self.alumno,
                                               grupo=self.grupo_2)
        self.assertEqual(inscripcion.calificaciones_unidad.count(), 2)


class PruebasPeriodos(BaseSistema):
    def test_solo_un_periodo_puede_estar_activo(self):
        nuevo = Periodo.objects.create(nombre='2026-2', activo=True)

        self.periodo.refresh_from_db()
        self.periodo_anterior.refresh_from_db()
        self.assertFalse(self.periodo.activo)
        self.assertFalse(self.periodo_anterior.activo)
        self.assertEqual(Periodo.actual().pk, nuevo.pk)

    def test_activar_desde_la_pantalla(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.post(reverse('periodo_activar'), {
            'periodo': self.periodo_anterior.pk,
            'siguiente': reverse('periodo_list'),
        })

        self.assertRedirects(respuesta, reverse('periodo_list'))
        self.assertEqual(Periodo.actual().pk, self.periodo_anterior.pk)

    def test_el_selector_del_encabezado_devuelve_a_la_pagina_actual(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.post(reverse('periodo_activar'), {
            'periodo': self.periodo_anterior.pk,
            'siguiente': reverse('grupo_list'),
        })

        self.assertRedirects(respuesta, reverse('grupo_list'))

    def test_al_activar_un_periodo_el_filtro_de_grupos_lo_sigue(self):
        """El filtro `?periodo=` de la tabla se actualiza al cambiar el vigente."""
        self.client.force_login(self.coordinador)
        destino = f"{reverse('grupo_list')}?periodo={self.periodo.pk}"

        respuesta = self.client.post(reverse('periodo_activar'), {
            'periodo': self.periodo_anterior.pk, 'siguiente': destino})

        self.assertRedirects(respuesta,
                             f"{reverse('grupo_list')}?periodo="
                             f"{self.periodo_anterior.pk}",
                             fetch_redirect_response=False)
        self.assertEqual(Periodo.actual().pk, self.periodo_anterior.pk)

        # Y la tabla ya muestra los grupos del periodo nuevo.
        pagina = self.client.get(respuesta.url)
        self.assertEqual(pagina.context['periodo_seleccionado'],
                         self.periodo_anterior)

    def test_el_periodo_activo_aparece_en_el_encabezado(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.get(reverse('grupo_list'))

        self.assertEqual(respuesta.context['periodo_activo'], self.periodo)
        self.assertContains(respuesta, self.periodo.nombre)

    def test_el_estudiante_solo_ve_el_periodo_sin_selector(self):
        self.client.force_login(self.estudiante)
        respuesta = self.client.get(reverse('mi_inscripcion'))

        self.assertContains(respuesta, self.periodo.nombre)
        self.assertNotContains(respuesta, reverse('periodo_activar'))

    def test_el_periodo_no_se_puede_borrar_si_tiene_grupos(self):
        self.client.force_login(self.coordinador)
        self.assertEqual(
            self.client.get(
                reverse('periodo_delete', args=[self.periodo.pk])).status_code,
            200)

        respuesta = self.client.post(
            reverse('periodo_delete', args=[self.periodo.pk]), follow=True)

        self.assertRedirects(respuesta, reverse('periodo_list'))
        self.assertContains(respuesta, 'no se puede eliminar')
        self.assertTrue(Periodo.objects.filter(pk=self.periodo.pk).exists())

    def test_un_periodo_sin_grupos_si_se_borra(self):
        self.client.force_login(self.coordinador)
        vacio = Periodo.objects.create(nombre='2026-3', activo=False)

        self.client.post(reverse('periodo_delete', args=[vacio.pk]))

        self.assertFalse(Periodo.objects.filter(pk=vacio.pk).exists())


class PruebasUsuarios(BaseSistema):
    def test_listado_muestra_alumnos_y_personal(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('usuario_list'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.coordinador.username)
        self.assertContains(respuesta, self.alumno.matricula)

    def test_alta_de_personal_como_administrador(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse('usuario_create_personal'), {
            'username': 'nuevoadmin', 'nombre': 'Nueva Jefa',
            'rol': 'ADMINISTRADOR', 'password_inicial': 'clave-de-prueba',
        })

        self.assertRedirects(respuesta, reverse('usuario_list'))
        perfil = Perfil.objects.get(usuario__username='nuevoadmin')
        self.assertEqual(perfil.rol, 'ADMINISTRADOR')
        self.assertTrue(self.client.login(username='nuevoadmin',
                                          password='clave-de-prueba'))

    def test_el_coordinador_no_puede_crear_administradores(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.get(reverse('usuario_create_personal'))
        roles = [codigo for codigo, _ in respuesta.context['form'].fields['rol'].choices]
        self.assertNotIn('ADMINISTRADOR', roles)
        self.assertIn('COORDINADOR', roles)

        respuesta = self.client.post(reverse('usuario_create_personal'), {
            'username': 'intruso', 'nombre': 'Intruso',
            'rol': 'ADMINISTRADOR', 'password_inicial': 'clave-de-prueba',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(User.objects.filter(username='intruso').exists())

    def test_el_formulario_de_edicion_se_abre_para_cualquier_usuario(self):
        """También para un superusuario que todavía no tiene Perfil."""
        self.client.force_login(self.admin)
        for usuario in [self.coordinador, self.estudiante]:
            with self.subTest(usuario=usuario.username):
                respuesta = self.client.get(
                    reverse('usuario_update', args=[usuario.pk]))
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.context['usuario'], usuario)

        superusuario = User.objects.create_superuser(
            username='root', password='clave-de-prueba', email='root@escuela.mx')
        respuesta = self.client.get(
            reverse('usuario_update', args=[superusuario.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['usuario'], superusuario)
        self.assertIsNone(respuesta.context['perfil'])

    def test_cambio_de_rol_y_bloqueo_de_acceso(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse('usuario_update', args=[self.coordinador.pk]),
            {'first_name': 'Coordinación General', 'rol': 'COORDINADOR',
             'is_active': ''},
        )

        self.assertRedirects(respuesta, reverse('usuario_list'))
        self.coordinador.refresh_from_db()
        self.assertEqual(self.coordinador.first_name, 'Coordinación General')
        self.assertFalse(self.coordinador.is_active)

    def test_el_administrador_tambien_puede_darse_de_baja_usuarios(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('usuario_create_personal'), {
            'username': 'temporal', 'nombre': 'Temporal',
            'rol': 'COORDINADOR', 'password_inicial': 'clave-de-prueba',
        })
        temporal = User.objects.get(username='temporal')

        self.client.post(reverse('usuario_delete', args=[temporal.pk]))
        self.assertFalse(User.objects.filter(username='temporal').exists())

    def test_no_se_borra_el_usuario_de_un_alumno(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse('usuario_delete', args=[self.estudiante.pk]), follow=True)

        self.assertRedirects(respuesta, reverse('usuario_list'))
        self.assertTrue(User.objects.filter(pk=self.estudiante.pk).exists())

    def test_asignar_contrasena_a_alumno_existente(self):
        self.client.force_login(self.admin)
        sin_usuario = Alumno.objects.create(
            matricula='20260077', nombre='Pedro Sin Acceso', semestre=1,
            carrera=self.carrera)

        url = reverse('usuario_create_alumno_existente')
        self.client.post(url, {'alumno': sin_usuario.pk,
                               'password_inicial': 'alumno123'})
        self.assertTrue(self.client.login(username='20260077',
                                          password='alumno123'))

        # Una vez con usuario, deja de aparecer en la lista de pendientes.
        self.client.force_login(self.admin)
        respuesta = self.client.post(url, {'alumno': sin_usuario.pk,
                                           'password_inicial': 'alumno123'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Perfil.objects.filter(alumno=sin_usuario).count(), 1)

    def test_cambio_de_contrasena(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse('usuario_password', args=[self.estudiante.pk]),
            {'password': 'nueva-clave-2026', 'repetir': 'nueva-clave-2026'})

        self.assertRedirects(respuesta, reverse('usuario_list'))
        self.assertTrue(self.client.login(username='20260001',
                                          password='nueva-clave-2026'))

    def test_la_contrasena_no_se_confirma_si_no_coincide(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse('usuario_password', args=[self.estudiante.pk]),
            {'password': 'nueva-clave-2026', 'repetir': 'otra-cosa'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(self.client.login(username='20260001',
                                          password='clave-de-prueba'))


class PruebasSembrarDemo(BaseSistema):
    """El comando `sembrar_demo` deja el sistema listo para probar."""

    def ejecutar(self, **opciones):
        return call_command('sembrar_demo', stdout=StringIO(), **opciones)

    def test_crea_los_usuarios_y_el_periodo_de_demo(self):
        self.ejecutar()

        coordinador = User.objects.get(username='coordinador')
        self.assertEqual(coordinador.perfil.rol, 'COORDINADOR')
        self.assertTrue(self.client.login(username='coordinador',
                                          password='coordinador123'))
        self.assertEqual(Perfil.objects.get(
            alumno=self.alumno).rol, 'ESTUDIANTE')

        periodo = Periodo.objects.get(nombre='2026-2')
        self.assertFalse(periodo.activo)
        self.assertEqual(Grupo.objects.filter(periodo=periodo).count(), 3)

    def test_se_puede_ejecutar_dos_veces_sin_duplicar(self):
        self.ejecutar()
        self.ejecutar(activar=True)

        self.assertEqual(Periodo.objects.filter(nombre='2026-2').count(), 1)
        self.assertEqual(Grupo.objects.filter(
            periodo__nombre='2026-2').count(), 3)
        self.assertEqual(Periodo.actual().nombre, '2026-2')

    def test_no_hace_nada_si_no_hay_alumnos(self):
        Alumno.objects.all().delete()
        with self.assertRaises(SystemExit):
            self.ejecutar()
