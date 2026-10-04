"""Pruebas de roles, permisos e inscripción del sistema escolar."""

from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Alumno, Calificacion, Carrera, Grupo, Materia, Perfil
from .services import ErrorInscripcion, desinscribir_alumno, inscribir_alumno

PERIODO = settings.PERIODO_ACTUAL


class BaseSistema(TestCase):
    """Datos mínimos: dos carreras, dos alumnos y tres grupos."""

    @classmethod
    def setUpTestData(cls):
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
            materia=cls.materia_1, periodo=PERIODO, cupo=30, num_alumnos=0,
            horario='L-V 08:00-09:30', aula='A-101', turno='MAT')
        cls.grupo_2 = Grupo.objects.create(
            materia=cls.materia_2, periodo=PERIODO, cupo=1, num_alumnos=0,
            horario='L-V 10:00-11:30', aula='B-204', turno='VES')
        cls.grupo_ajeno = Grupo.objects.create(
            materia=cls.materia_ajena, periodo=PERIODO, cupo=30, num_alumnos=0,
            horario='L-V 12:00-13:30', aula='C-101', turno='MAT')

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
        for url in ['index', 'alumno_list', 'grupo_list', 'mi_inscripcion',
                    'mi_carga_academica', 'alumno_create', 'carrera_create']:
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
        for url in ['alumno_list', 'alumno_create', 'carrera_list',
                    'carrera_create', 'materia_list', 'materia_create']:
            with self.subTest(url=url):
                respuesta = self.obtener(reverse(url))
                self.assertEqual(respuesta.status_code, 200)

    def test_coordinador_gestiona_grupos_pero_no_da_alta_de_alumnos(self):
        self.client.force_login(self.coordinador)
        for url in ['grupo_list', 'grupo_create', 'inscripcion_alumnos']:
            with self.subTest(url=url):
                self.assertEqual(self.obtener(reverse(url)).status_code, 200)

        for url in ['alumno_create', 'carrera_create', 'materia_create']:
            with self.subTest(url=url):
                respuesta = self.obtener(reverse(url))
                self.assertRedirects(respuesta, reverse('index'))

    def test_estudiante_solo_accede_a_sus_operaciones(self):
        self.client.force_login(self.estudiante)
        self.assertEqual(
            self.obtener(reverse('mi_inscripcion')).status_code, 200)
        self.assertEqual(
            self.obtener(reverse('mi_carga_academica')).status_code, 200)

        for url in ['alumno_list', 'carrera_list', 'materia_list',
                    'grupo_list', 'grupo_create', 'alumno_create',
                    'inscripcion_alumnos', 'carrera_create', 'materia_create']:
            with self.subTest(url=url):
                respuesta = self.obtener(reverse(url))
                self.assertRedirects(respuesta, reverse('index'))

    def test_estudiante_no_modifica_calificaciones(self):
        self.client.force_login(self.estudiante)
        url = reverse('alumno_cardex', args=[self.alumno.matricula])
        self.assertRedirects(self.client.get(url), reverse('index'))

    def test_solo_coordinador_modifica_calificaciones(self):
        self.client.force_login(self.coordinador)
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
        for url in ['grupo_list', 'inscripcion_alumnos', 'alumno_create',
                    'alumno_list']:
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
        respuesta = self.client.post(reverse('alumno_create'), datos)
        self.assertRedirects(respuesta, reverse('alumno_list'))

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
        respuesta = self.client.post(reverse('alumno_create'), datos)
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
            'materia': self.materia_1.pk, 'periodo': PERIODO,
            'turno': 'MAT', 'horario': 'L-V 07:00-08:30', 'aula': 'A-102',
            'cupo': 25, 'num_alumnos': 0,
        })
        self.assertRedirects(respuesta, reverse('grupo_list'))
        self.assertTrue(
            Grupo.objects.filter(horario='L-V 07:00-08:30').exists())

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
        respuesta = self.client.post(reverse('alumno_create'), datos)
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
        Calificacion.objects.create(alumno=self.alumno, grupo=self.grupo_1)
        self.grupo_1.num_alumnos = 1
        self.grupo_1.save(update_fields=['num_alumnos'])

        self.client.force_login(self.estudiante)
        respuesta = self.client.post(reverse('mi_inscripcion'),
                                     {'grupos': [self.grupo_2.pk]},
                                     follow=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'ya tiene una carga académica activa')
        self.assertFalse(
            Calificacion.objects.filter(alumno=self.alumno,
                                        grupo=self.grupo_2).exists())

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
        cursada = Calificacion.objects.create(
            alumno=self.alumno, grupo=self.grupo_1, valor=Decimal('8.5'))
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
        Grupo.objects.create(materia=self.materia_1, periodo='2025-2', cupo=10,
                             num_alumnos=0, horario='L-V 09:00-10:30')
        grupo_antiguo = Grupo.objects.get(periodo='2025-2')
        with self.assertRaisesMessage(ErrorInscripcion, 'inscripción está abierta'):
            inscribir_alumno(self.alumno, [grupo_antiguo])

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
        respuesta = self.client.post(url, {'quitar': [calificacion.pk]})

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(
            Calificacion.objects.filter(pk=calificacion.pk).exists())
        self.grupo_1.refresh_from_db()
        self.assertEqual(self.grupo_1.num_alumnos, 0)

    def test_el_estudiante_no_puede_darse_de_baja(self):
        calificacion = Calificacion.objects.create(
            alumno=self.alumno, grupo=self.grupo_1)
        self.client.force_login(self.estudiante)
        respuesta = self.client.post(reverse('mi_inscripcion'),
                                     {'quitar': [calificacion.pk]})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(
            Calificacion.objects.filter(pk=calificacion.pk).exists())

    def test_lista_de_materias_muestra_motivos_de_bloqueo(self):
        cursada = Calificacion.objects.create(
            alumno=self.alumno, grupo=self.grupo_1)
        cursada.grupo.num_alumnos = 1
        cursada.grupo.save(update_fields=['num_alumnos'])
        Grupo.objects.filter(pk=self.grupo_2.pk).update(num_alumnos=1)

        self.client.force_login(self.estudiante)
        respuesta = self.client.get(reverse('mi_inscripcion'))

        self.assertContains(respuesta, 'Materia ya cursada')
        self.assertContains(respuesta, 'Grupo sin cupo')
        self.assertContains(respuesta, 'No hay materias disponibles')

    def test_desinscribir_no_deja_num_alumnos_negativo(self):
        calificacion = Calificacion.objects.create(
            alumno=self.alumno, grupo=self.grupo_1)
        desinscribir_alumno(self.alumno, [calificacion])
        self.grupo_1.refresh_from_db()
        self.assertEqual(self.grupo_1.num_alumnos, 0)


class PruebasCargaAcademica(BaseSistema):
    def setUp(self):
        Calificacion.objects.create(alumno=self.alumno, grupo=self.grupo_1,
                                    valor=Decimal('9.0'))
        Calificacion.objects.create(alumno=self.alumno, grupo=self.grupo_2)

    def test_coordinador_consulta_carga_de_cualquier_alumno(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.get(
            reverse('carga_de_alumno', args=[self.alumno.matricula]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Matemáticas I')
        self.assertContains(respuesta, 'Aprobada')
        self.assertContains(respuesta, 'En curso')

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
        self.assertEqual(self.alumno.promedio_general, Decimal('9.0'))
        self.assertTrue(self.alumno.tiene_carga_activa)


class PruebasCardex(BaseSistema):
    def test_coordinador_guarda_calificaciones_finales(self):
        Calificacion.objects.create(alumno=self.alumno, grupo=self.grupo_1)
        self.client.force_login(self.coordinador)
        url = reverse('alumno_cardex', args=[self.alumno.matricula])
        respuesta = self.client.get(url)
        calificacion_id = respuesta.context['formset'].forms[0]['id'].value()

        respuesta = self.client.post(url, {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            f'form-0-id': calificacion_id,
            'form-0-valor': '7.5',
        })

        self.assertEqual(respuesta.status_code, 302)
        calificacion = Calificacion.objects.get(alumno=self.alumno,
                                                grupo=self.grupo_1)
        self.assertEqual(calificacion.valor, Decimal('7.5'))
        self.assertIsNotNone(calificacion.fecha_captura)

    def test_rechaza_calificacion_fuera_de_rango(self):
        Calificacion.objects.create(alumno=self.alumno, grupo=self.grupo_1)
        self.client.force_login(self.coordinador)
        url = reverse('alumno_cardex', args=[self.alumno.matricula])
        respuesta = self.client.get(url)
        calificacion_id = respuesta.context['formset'].forms[0]['id'].value()

        respuesta = self.client.post(url, {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            f'form-0-id': calificacion_id,
            'form-0-valor': '12',
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            Calificacion.objects.get(grupo=self.grupo_1).valor, None)