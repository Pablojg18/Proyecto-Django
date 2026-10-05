# Documento de Cambios — Proyecto Django

Documento que registra todos los cambios realizados sobre el proyecto, indicando **qué** se hizo y **dónde** se implementó.

---

## 1. Configuración del entorno virtual (`entorno`)

| Qué | Dónde |
|---|---|
| Creación del entorno virtual con `python -m venv` | Carpeta `entorno/` (raíz del proyecto) |
| Instalación de Django 6.1.1 + drivers | `entorno/Lib/site-packages/` |
| Paquetes instalados: `django==6.1.1`, `PyMySQL 1.2.3`, `cryptography`, `cffi`, `pycparser` | `entorno/` |

## 2. Carga del proyecto con sus modelos

| Qué | Dónde |
|---|---|
| Verificación de migraciones y modelos cargados | `academico/models.py` (modelos `Carrera`, `Materia`, `Grupo`, `Alumno`, `Calificacion`) |
| Migración aplicada (tablas creadas) | `academico/migrations/0001_initial.py` |

## 3. Módulo de administración activado (más de 2 modelos)

| Qué | Dónde |
|---|---|
| Registro de los 5 modelos en el admin de Django | `academico/admin.py` (`CarreraAdmin`, `MateriaAdmin`, `GrupoAdmin`, `AlumnoAdmin`, `CalificacionAdmin`) |
| Superusuario `admin` creado con `createsuperuser` | Base de datos (tabla `auth_user`) |

## 4. Plantilla de lista con DataTables y exportación a Excel

| Qué | Dónde |
|---|---|
| Nueva plantilla tipo lista para el modelo `Alumno` | `academico/templates/academico/alumno_list.html` |
| Inicialización de DataTables.net (CDN) | `alumno_list.html` (bloque `<script>`) |
| Botón "Exportar a Excel" (`excelHtml5`) + JSZip | `alumno_list.html` (botones DataTables) |
| Vista `alumno_list` que alimenta los datos | `academico/views.py` |
| Ruta `/alumnos/` | `escolar_project/urls.py` |
| Enlace desde la portada | `academico/templates/academico/index.html` |

## 5. Corrección de configuración

| Qué | Dónde |
|---|---|
| `ALLOWED_HOSTS` estaba vacío → se añadieron `localhost`, `127.0.0.1`, `testserver` | `escolar_project/settings.py` |

## 6. Migración de SQLite → MySQL

| Qué | Dónde |
|---|---|
| Instalación de driver `PyMySQL` | `entorno/` |
| Configuración de la conexión MySQL (BD `escolar`, puerto `3307`, usuario `root`) | `escolar_project/settings.py` (bloque `DATABASES`) |
| Registro del backend de PyMySQL como `MySQLdb` | `escolar_project/__init__.py` |
| Migración completa ejecutada contra MySQL 8.4.11 | Base de datos MySQL `escolar` (tablas de academico, auth, admin, contenttypes, sessions) |
| Datos migrados desde `db.sqlite3` (3 carreras, 1 materia, 1 grupo, 2 alumnos, 1 calificación) | Base de datos MySQL `escolar` |
| Instalación de MySQL 8.4.11 en `%LOCALAPPDATA%\mysql84` (instancia independiente, no toca el MySQL 8.0 existente) | `%LOCALAPPDATA%\mysql84\mysql-8.4.11-winx64` |
| Superusuario `admin` recreado en MariaDB con `createsuperuser` | Base de datos MariaDB (tabla `auth_user`) |

## 7. Scripts de arranque

| Qué | Dónde |
|---|---|
| Script para levantar MySQL 8.4 en el puerto 3307 | `iniciar_mysql84.bat` (raíz) |
| Script para activar el entorno virtual y ejecutar `runserver` | `iniciar_servidor.bat` (raíz) |

## 8. Archivos de control de versiones

| Qué | Dónde |
|---|---|
| Reglas de exclusión para git (entorno, BD, cachés Python, IDE) | `.gitignore` (raíz) |
| Este documento | `DOCUMENTO_DE_CAMBIOS.md` (raíz) |

## 9. Promedio general y cardex de alumnos

| Qué | Dónde |
|---|---|
| Propiedad `materias_cursadas` (inscripciones del alumno) | `academico/models.py` (`Alumno`) |
| Propiedad `promedio_general` (promedio de las materias ya calificadas; `None` si no hay ninguna) | `academico/models.py` (`Alumno`) |
| Formulario de captura de calificación final por materia | `academico/forms.py` (`CalificacionForm`, `CalificacionFormSet`) |
| Columnas "Materias cursadas", "Promedio general" y botón "Cardex" en la lista | `academico/templates/academico/alumno_list.html` |
| Ordenamiento numérico de las columnas numéricas y exclusión del botón en la exportación | `alumno_list.html` (bloque `<script>`, `columnDefs`) |
| Vista `alumno_cardex` (GET muestra el formulario, POST guarda y fija `fecha_captura`) | `academico/views.py` |
| Formulario con la lista de materias cursadas y sus calificaciones | `academico/templates/academico/alumno_cardex.html` |
| Ruta `/alumnos/<matricula>/cardex/` | `escolar_project/urls.py` |
| `prefetch_related('calificaciones')` para evitar consultas por alumno | `academico/views.py` (`alumno_list`) |

## 10. Base de datos en MariaDB y proyecto simplificado

| Qué | Dónde |
|---|---|
| Base de datos `escolar` creada con `utf8mb4` y migraciones aplicadas | Base de datos MariaDB `escolar` (servicio `MariaDB`, puerto 3307) |
| Verificación: 15 pruebas contra MariaDB y flujo completo por HTTP (listado, cardex, guardado de calificaciones) | Ejecución local, no se agrega archivo al proyecto |
| Datos de ejemplo (2 carreras, 3 materias, 3 grupos, 3 alumnos, 5 calificaciones), sobre los registros que ya venían de la base original | Base de datos `escolar` |
| Eliminados los scripts de arranque: el servicio `MariaDB` ya inicia solo con Windows y `runserver` se lanza a mano | `iniciar_mysql84.bat`, `iniciar_servidor.bat` (raíz) |
| Eliminada la configuración de correo `MAILERS`, que no era una opción válida de Django | `escolar_project/settings.py` |
| Portada convertida en un menú con dos enlaces, en vez de un volcado de las 5 tablas | `academico/templates/academico/index.html` |
| Vista `index` sin consultas a la base de datos | `academico/views.py` |
| Eliminadas las importaciones sin uso (`Carrera`, `Materia`, `Grupo`) | `academico/views.py` |
| Eliminados `asgi.py` (solo se usa `wsgi.py`) y `academico/tests.py` (estaba vacío) | `escolar_project/asgi.py`, `academico/tests.py` |

> **Nota:** el servidor del puerto 3307 es **MariaDB 12.1.2** (servicio de Windows con inicio
> automático), no la instalación portátil de MySQL 8.4 que describía `iniciar_mysql84.bat`.
> La configuración de `settings.py` no cambia porque `django.db.backends.mysql` también
> sirve para MariaDB mediante PyMySQL. Para levantar el proyecto:

```
python manage.py migrate
python manage.py runserver
```

---

## 11. Roles de usuario y control de acceso

| Qué | Dónde |
|---|---|
| Modelo `Perfil` (1:1 con `User`) con `rol` (`ADMINISTRADOR`, `COORDINADOR`, `ESTUDIANTE`) y `alumno` asociado opcional, con `clean()` que exige alumno solo al estudiante | `academico/models.py` |
| `Alumno.delete()` borra también el usuario de acceso del alumno | `academico/models.py` |
| Migración del modelo y de datos que deja a los superusuarios como administradores | `academico/migrations/0002_perfil.py`, `0003_asigna_rol_administrador.py` |
| `requiere_rol(*roles)` para vistas de función y `RolRequeridoMixin` para vistas de clase; ambos exigen sesión iniciada ydevuelven al inicio con mensaje si el rol no corresponde | `academico/permisos.py` |
| `perfil_de`, `rol_de`, `es_alumno_del_usuario` como consultas de apoyo | `academico/permisos.py` |
| Contexto `perfil`, `es_admin`, `es_coordinador`, `es_estudiante` para el menú según rol | `academico/context_processors.py` |
| Inicio y cierre de sesión con `LoginView`/`LogoutView` (el cierre es por POST) | `academico/views/cuentas.py` |
| Plantilla de acceso con explicación de los tres roles | `academico/templates/registration/login.html` |
| Menú por rol, indicador de rol y botón de cerrar sesión | `academico/templates/academico/base.html` |
| Portada convertida en tablero: resumen del rol y lista de operaciones permitidas | `academico/templates/academico/index.html` |
| `PERIODO_ACTUAL`, `CALIFICACION_APROBADA`, `LOGIN_URL`, `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL`, idioma `es-mx` y zona horaria `America/Mexico_City` | `escolar_project/settings.py` |
| Rutas de sesión y de todas las operaciones | `escolar_project/urls.py` |

Matriz de permisos implementada:

| Operación | Administrador | Coordinador | Estudiante |
|---|---|---|---|
| Alta, edición y baja de alumnos, carreras y materias | Sí | No | No |
| Consulta de alumnos, carreras y materias | Sí | Sí | No |
| Alta, edición y baja de grupos | Sí | Sí | No |
| Alta, edición y baja de periodos y cambio del vigente | Sí | Sí | No |
| Inscripción de alumnos (elegir alumno y materias) | Sí | Sí | No |
| Inscripción propia | No | No | Sí (sin carga activa) |
| Consulta de carga académica | Sí | Sí | Sí (solo la propia) |
| Captura de calificaciones finales (cardex) | Sí | Sí | No |
| Consulta de cardex | Sí | Sí | Sí (el propio, sin editar) |
| Gestión de usuarios (alta, edición, contraseña y baja) | Sí | Sí (sin crear administradores) | No |

> El superusuario de `/admin/` ignora la matriz anterior para poder revisar todo el
> sistema; cualquier otro usuario queda sujeto a su rol.

## 12. Catálogos con altas, ediciones y bajas

| Qué | Dónde |
|---|---|
| Vistas genéricas `ListView`, `CreateView`, `UpdateView` y `DeleteView` por catálogo | `academico/views/catalogos.py` |
| Formularios de alumno (con usuario), carrera, materia y grupo | `academico/forms.py` |
| `AlumnoForm` crea el usuario con la matrícula como nombre de acceso y exige contraseña inicial al dar de alta | `academico/forms.py` |
| Plantilla común de alta/edición y de confirmación de baja | `academico/templates/academico/form_generico.html`, `confirmar_borrado.html` |
| Listados con DataTables y exportación a Excel, con acciones según el rol | `academico/templates/academico/{alumno,carrera,materia,grupo}_list.html` |
| Campos derivados en los listados: materias y alumnos por carrera, grupos por materia, lugares libres por grupo | `academico/models.py` (`Grupo.lugares_disponibles`), vistas de catálogo |

## 13. Inscripción de materias

| Qué | Dónde |
|---|---|
| Servicio `inscribir_alumno` con validación de reglas y transacción atómica; el coordinador usa `forzar=True` | `academico/services.py` |
| Servicio `desinscribir_alumno` que libera lugares del grupo | `academico/services.py` |
| Reglas: periodo vigente, materia de la carrera del alumno, materia no cursada, grupo con cupo, sin inscripción duplicada y sin carga académica activa para el estudiante | `academico/services.py` |
| `GruposChoiceField` con checkboxs que muestran código, nombre, turno, horario, aula y lugares libres | `academico/forms.py` |
| `grupos_inscribibles` devuelve cada grupo del periodo con su motivo de bloqueo | `academico/forms.py` |
| Paso 1 del coordinador: elegir alumno con filtros de búsqueda y carrera | `academico/views/inscripcion.py` (`AlumnosParaInscribir`) |
| Paso 2 del coordinador y del estudiante: misma pantalla reutilizada, con opción de dar de baja inscripciones solo para el coordinador | `academico/views/inscripcion.py` (`InscripcionBase`, `InscripcionCoordinador`, `MiInscripcion`) |
| Pantalla de inscripción con materias del periodo, motivo de las no disponibles y materias ya inscritas | `academico/templates/academico/inscripcion.html` |
| Pantalla de selección de alumno | `academico/templates/academico/inscripcion_alumnos.html` |
| Rutas `/inscripcion/`, `/coordinacion/inscripcion/` y `/coordinacion/inscripcion/<matricula>/` | `escolar_project/urls.py` |

## 14. Carga académica

| Qué | Dónde |
|---|---|
| Propiedades de cálculo: `carga_academica`, `tiene_carga_activa`, `ha_cursado`, `materias_aprobadas`, `creditos_acumulados`, `creditos_en_curso`, `avance_carrera` | `academico/models.py` (`Alumno`) |
| `Calificacion.es_aprobada` a partir de `CALIFICACION_APROBADA` | `academico/models.py` (`Calificacion`) |
| Consulta por parte del coordinador o administrador | `academico/views/carga.py` (`carga_de_alumno`) |
| Consulta del estudiante sobre su propio registro | `academico/views/carga.py` (`mi_carga_academica`) |
| Pantalla con resumen, datos del alumno, carga del periodo e historial con situación de cada materia | `academico/templates/academico/carga_academica.html` |
| Rutas `/alumnos/<matricula>/carga/` y `/mi-carga-academica/` | `escolar_project/urls.py` |

La captura de calificaciones finales de la tarea anterior se conserva en
`academico/views/cardex.py`, ahora protegida para coordinador y administrador.

## 15. Pruebas y usuarios de demostración

| Qué | Dónde |
|---|---|
| 63 pruebas: sesión, matriz de permisos por rol, CRUD de los cuatro catálogos, reglas de inscripción, carga académica, gestión de usuarios y periodos | `academico/tests.py` |
| Comando que crea un coordinador y un usuario por cada alumno, para probar los tres roles | `academico/management/commands/crear_usuarios_demo.py` |
| Comando que crea el periodo `2026-2` con las materias `MAT103` y `MAT104` listas para inscripciones | `academico/management/commands/sembrar_periodo_demo.py` |
| Registro del modelo `Perfil` en el admin de Django | `academico/admin.py` |

Comandos de apoyo:

```
python manage.py test academico
python manage.py crear_usuarios_demo
python manage.py sembrar_periodo_demo --activar
```

Accesos de prueba que deja el comando:

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | el superusuario creado con `createsuperuser` | la que se defina |
| Coordinador | `coordinador` | `coordinador123` |
| Estudiante | la matrícula de cada alumno | `alumno123` |

> El periodo vigente ya no se cambia editando `PERIODO_ACTUAL` en `settings.py`: se
> cambia desde la pantalla **Periodos** o con el selector del encabezado. Ese valor en
> `settings.py` solo sirve para sembrar el periodo inicial.

---

## 16. Periodo académico, pantalla de usuarios y cardex del estudiante

| Qué | Dónde |
|---|---|
| Modelo `Periodo` (nombre único, `activo`, `save()` que desactiva el resto, `Periodo.actual()` y `Periodo.activar()`) | `academico/models.py` |
| `Grupo.periodo` como clave foránea obligatoria; `Grupo.lugares_disponibles` sigue funcionando igual | `academico/models.py` |
| Migración que convierte la columna textual `periodo` del grupo en FK, crea `2026-1` (activo) y `AGO-DIC` (histórico) y conserva los 3 grupos existentes | `academico/migrations/0005_periodo.py` |
| `PERIODO_ACTUAL` pasa a ser solo el nombre del periodo que se siembra | `escolar_project/settings.py` |
| Servicios de inscripción, cardex y carga leen el periodo vigente de la base de datos | `academico/services.py`, `academico/views/carga.py` |
| Pantalla **Periodos**: alta, edición, borrado (protegido si tiene grupos) y activación | `academico/views/catalogos.py` (`PeriodoListView`, `PeriodoCreateView`, `PeriodoUpdateView`, `PeriodoDeleteView`, `PeriodoActivarView`) |
| Selector del periodo vigente en el encabezado, con retorno a la página de origen | `academico/templates/academico/base.html` |
| Periodo activo y lista de periodos disponibles para las plantillas | `academico/context_processors.py` |
| Formularios `PeriodoForm`, `AlumnoForm`, `AlumnosSinUsuario`, `UsuarioPersonalForm`, `UsuarioEdicionForm` y `PasswordForm` | `academico/forms.py` |
| Pantalla central **Usuarios**: alta de alumno, alta de alumno existente, alta de personal, edición de rol y estado, contraseña y baja protegida | `academico/views/usuarios.py` |
| `/alumnos/nuevo/` deja de dar de alta y redirige a la pantalla de usuarios | `escolar_project/urls.py` (`alumno_create`), `academico/views/usuarios.py` (`usuario_redirect_alumno`) |
| Plantillas de usuarios y de periodos | `academico/templates/academico/usuarios*.html`, `periodo_list.html` |
| `mi_cardex` de solo lectura para el estudiante, que sigue viendo su historial en modo consulta | `academico/views/cardex.py`, `academico/templates/academico/alumno_cardex.html` |
| Portada con tarjetas por operación según el rol | `academico/views/cuentas.py`, `academico/templates/academico/index.html` |
| Plantilla de grupo con el periodo de cada grupo y filtro por periodo | `academico/templates/academico/grupo_list.html` |

Datos de demostración del periodo siguiente:

```
python manage.py sembrar_periodo_demo            # crea 2026-2 sin activarlo
python manage.py sembrar_periodo_demo --activar  # además lo deja vigente
```

> `MAT101` y `MAT102` ya están cursadas por los alumnos existentes, por eso el comando
> siembra `MAT103` y `MAT104`. Un alumno con carga activa en `2026-1` tampoco puede
> inscribirse hasta que se desinscriba o termine el periodo.


---

## Historial de commits

1. `init: andamiaje de Django y modelos del módulo académico` — estructura del proyecto, app `academico` con sus modelos y migraciones.
2. `feat: plantilla de lista con DataTables y exportación a Excel` — vista, ruta y plantilla `alumno_list` con botones DataTables.
3. `feat: migración a base de datos MySQL` — configuración `DATABASES`, backend PyMySQL y ajustes de conexión.
4. `docs: documento de cambios y correcciones de configuración` — este documento, `.gitignore`, `ALLOWED_HOSTS` y scripts de arranque.
5. `fix: agrega archivos asgi y wsgi del proyecto Django` — archivos de entrada ASGI/WSGI faltantes.
6. `feat: promedio general y cardex de alumnos` — propiedades de promedio en el modelo, formulario de captura de calificación final y vista de cardex.
7. `chore: base de datos en MariaDB y proyecto simplificado` — se crea y migra la base `escolar`, se eliminan los scripts `.bat`, `asgi.py` y `tests.py`, y la portada pasa a ser un menú.
8. `feat: roles, catalogos, inscripcion y carga academica` — perfil con rol e inicio de sesión, CRUD de alumnos, carreras, materias y grupos, reglas de inscripción y consulta de carga académica, con sus pruebas.
9. `feat: periodo academico, pantalla de usuarios y cardex del estudiante` — `Periodo` como clave foránea de `Grupo` con pantalla y selector de periodo vigente, gestión centralizada de usuarios y roles, cardex de solo lectura para el estudiante y datos de demostración de `2026-2`.