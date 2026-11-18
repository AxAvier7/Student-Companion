# Guía para estudiantes: usa Student Support con tus propios grupos

Esta guía está pensada para alguien que **no ha programado antes**: explica desde cero cómo instalar la aplicación, conectar tu cuenta de Telegram y organizar los materiales de tus asignaturas. Todo se guarda en **tu ordenador**; el proyecto no envía tus archivos a ningún servidor.

- [1. Qué necesitas](#1-qué-necesitas)
- [2. Descargar el proyecto](#2-descargar-el-proyecto)
- [3. Instalar Python y la dependencia](#3-instalar-python-y-la-dependencia)
- [4. Obtener tus credenciales de Telegram](#4-obtener-tus-credenciales-de-telegram)
- [5. Primer inicio: iniciar sesión](#5-primer-inicio-iniciar-sesión)
- [6. Crear tu primera asignatura y añadir grupos](#6-crear-tu-primera-asignatura-y-añadir-grupos)
- [7. Sincronizar: bajar mensajes y archivos](#7-sincronizar-bajar-mensajes-y-archivos)
- [8. Uso diario: encontrar y abrir materiales](#8-uso-diario-encontrar-y-abrir-materiales)
- [9. Marcar profesores](#9-marcar-profesores)
- [10. Dónde se guardan tus archivos](#10-dónde-se-guardan-tus-archivos)
- [11. Mantenerlo actualizado](#11-mantenerlo-actualizado)
- [12. Privacidad y buenas prácticas](#12-privacidad-y-buenas-prácticas)
- [13. Solución de problemas](#13-solución-de-problemas)
- [14. Preguntas frecuentes](#14-preguntas-frecuentes)

---

## 1. Qué necesitas

| Necesitas | Para qué |
|---|---|
| Windows 10 u 11 | Es la plataforma probada. |
| Python 3.10 o superior (se recomienda 3.13) | Ejecuta la aplicación. |
| Una cuenta de Telegram | Lee los grupos con tu propio usuario. |
| `api_id` y `api_hash` gratuitos | Identifican tu aplicación ante Telegram. |
| Ser miembro de los grupos | Telegram solo permite leer el historial de los grupos a los que perteneces. |

No necesitas servidor, base de datos externa ni pagar nada. La base de datos SQLite se crea sola.

> **Importante:** unirse al grupo es un paso que haces tú en la app de Telegram, antes de usar esta herramienta. Si solo ves el grupo en una búsqueda pero no eres miembro, la descarga fallará.

---

## 2. Descargar el proyecto

**Opción A (recomendada): con Git**

Abre PowerShell en la carpeta donde quieras guardar el proyecto y escribe:

```powershell
git clone https://github.com/AxAvier7/Student-Companion.git
cd Student-Companion
```

**Opción B: sin Git**

Entra en <https://github.com/AxAvier7/Student-Companion>, pulsa el botón verde **Code** → **Download ZIP**, y descomprime el archivo. Después abre una terminal dentro de la carpeta descomprimida.

---

## 3. Instalar Python y la dependencia

1. Si no tienes Python, descárgalo de <https://www.python.org/downloads/> e instálalo **marcando la casilla “Add python.exe to PATH”**.
2. Comprueba que funciona:

   ```powershell
   python --version
   ```

   Debe mostrar algo como `Python 3.13.x`.

3. (Recomendado) Crea un entorno virtual para no mezclar librerías de otros proyectos:

   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

   Verás `(venv)` o `(.venv)` al principio de la línea.

4. Instala la única dependencia:

   ```powershell
   pip install -r requirements.txt
   ```

5. Arranca la aplicación:

   ```powershell
   python main.py
   ```

   También puedes hacer doble clic en **`Iniciar Student Support.bat`** (si usas entorno virtual, arráncala desde la terminal con el entorno activado).

---

## 4. Obtener tus credenciales de Telegram

Telethon necesita que le digas a Telegram quién es la aplicación que está leyendo los mensajes. Es gratuito y solo se hace una vez:

1. Entra en <https://my.telegram.org> desde el navegador.
2. Inicia sesión con tu número de teléfono de Telegram.
3. Pulsa **API development tools**.
4. Rellena el formulario, por ejemplo:
   - **App title:** `Student Support`
   - **Short name:** `studentsupport`
   - **Platform:** `Desktop`
   - **Description:** `Uso personal y académico`
5. Copia los valores **App api_id** (un número) y **App api_hash** (una cadena larga).

Trátalos como una contraseña: no los compartas ni los pegues en un issue, chat público o captura de pantalla.

---

## 5. Primer inicio: iniciar sesión

Al abrir la aplicación aparece la pantalla **Conectar con Telegram**:

1. Escribe el `api_id`, el `api_hash` y tu teléfono en formato internacional, por ejemplo `+34600123456` (en España) o `+5312345678`.
2. Pulsa **Guardar y conectar**.
3. Telegram te enviará un **código de verificación** al chat de “Telegram” dentro de tu app (no suele llegar por SMS). Escríbelo en el diálogo.
4. Si tienes activada la **verificación en dos pasos**, te pedirá también la contraseña de Telegram.

La sesión queda guardada en `data/telegram.session`. Las siguientes veces la app entra directamente, sin pedir el código.

> Si más tarde quieres cambiar de cuenta, usa **Telegram → Cerrar sesión de Telegram** en la barra superior y vuelve a iniciar sesión.

---

## 6. Crear tu primera asignatura y añadir grupos

Cada asignatura es una pestaña con sus propios grupos.

1. Pulsa **Nueva asignatura** (o `Ctrl+N`).
2. Escribe el nombre, por ejemplo `Matemáticas II`.
3. Busca el grupo o canal de Telegram de una de estas formas:
   - el **nombre completo**, por ejemplo `Matemáticas II - Grado`;
   - el **@usuario**, por ejemplo `@mateii_grado`;
   - un **enlace** `https://t.me/mateii_grado`.
4. La app busca primero entre **tus chats** y después en la **búsqueda global** de Telegram. Selecciona el resultado correcto con un clic. Puedes seleccionar varios manteniendo `Ctrl` o `Mayús` si la asignatura tiene varios grupos (por ejemplo, uno de teoría y otro de prácticas).
5. Pulsa **Crear asignatura**.
6. Responde que **sí** cuando pregunte si quieres sincronizar ahora.

Para añadir más grupos después: entra en la pestaña de la asignatura, usa el panel izquierdo → **Añadir**. Para quitar uno, selecciónalo y pulsa **Quitar** (esto solo borra el índice; tus archivos descargados no se eliminan).

**Si el grupo no aparece:** comprueba que eres miembro, prueba con el nombre oficial exacto o con el `@usuario`, y recuerda que los enlaces privados (`t.me/+...`) no se pueden resolver sin unirse primero.

---

## 7. Sincronizar: bajar mensajes y archivos

La sincronización es el proceso que lee el historial y guarda mensajes y archivos.

- **La primera vez** de cada grupo se revisa el historial desde la fecha límite configurada (por defecto, **1 de agosto de 2026**).
- **Las siguientes veces** solo se pide lo nuevo, así que son mucho más rápidas.
- Puedes pulsar **Sincronizar** en una pestaña o **Sincronizar todo** en la barra superior (`F5`).
- Si un grupo tiene mucho contenido (por ejemplo, vídeos grandes), la descarga puede tardar. Pulsa **Cancelar** en la barra inferior si quieres pararla; lo ya descargado se conserva.
- Si borras un archivo de tu disco, la siguiente sincronización detecta que falta en la carpeta y lo vuelve a descargar.

> **Cambiar la fecha límite.** El punto de partida está en `student_support/config.py`, en las constantes `MESSAGE_CUTOFF_LOCAL` (fecha) y `MESSAGE_CUTOFF_LABEL` (texto que aparece en la app). Por ejemplo, para empezar el 1 de septiembre de 2026:

```python
MESSAGE_CUTOFF_LOCAL = datetime(2026, 9, 1, 0, 0)
MESSAGE_CUTOFF_LABEL = "01/09/2026"
```

Guarda el archivo y reinicia la aplicación. Al hacerlo se descartan del índice y del disco los mensajes anteriores a esa fecha.

---

## 8. Uso diario: encontrar y abrir materiales

Dentro de la pestaña de una asignatura verás tres zonas:

- **Izquierda:** lista de grupos y número de mensajes de cada uno. Al seleccionar uno, la tabla muestra solo ese grupo; selecciona **Todos los canales** para verlos todos.
- **Centro:** tabla con fecha, quién lo subió, canal, tipo de contenido, texto y nombre del archivo.
- **Abajo:** detalle completo del mensaje seleccionado y botones para abrir el archivo, la carpeta o el mensaje en Telegram.

### Filtros

Puedes combinar todos a la vez:

| Filtro | Dónde | Qué hace |
|---|---|---|
| Texto | Campo **Buscar** | Busca en el mensaje, el remitente y el nombre del archivo. |
| Canal | Panel izquierdo | Limita la vista a un grupo. |
| Tipo | Desplegable **Tipo** | Documentos, imágenes, vídeos, audio, texto, enlaces u otros. |
| Profesores | Casilla **Solo profesores** | Muestra solo los mensajes de quienes hayas marcado como profesores. |

Cuando hay filtros activos, el contador añade «(filtrado)». El botón **Cargar más** muestra otros 800 mensajes sin perder los filtros.

### Abrir materiales

- **Doble clic** en un mensaje con archivo, o `Enter`, o el botón **Abrir archivo**: se abre con el programa predeterminado de Windows (PDF, Word, vídeo…).
- **Abrir carpeta**: abre la carpeta del grupo en el Explorador de Windows.
- **Ver en Telegram**: abre el mensaje original en tu navegador o app de Telegram.
- `Ctrl+C` copia el texto del mensaje seleccionado.

---

## 9. Marcar profesores

Cuando un grupo tiene muchos participantes, puedes distinguir los apuntes del profesorado:

1. Haz **clic derecho** sobre un mensaje suyo → **Marcar como profesor**.
2. O abre **Opciones → Profesores…**: aparecen todos los remitentes detectados, con el número de mensajes de cada uno. Haz doble clic en uno o usa los botones **Marcar como profesor** / **Quitar de profesores**.

Los profesores aparecen con una **★** delante de su nombre. Activa la casilla **Solo profesores** para ver únicamente sus mensajes; se puede combinar con la búsqueda, el tipo y el canal.

El marcado es **por asignatura**: si marcas a alguien en Matemáticas II, sus mensajes en todos los grupos de esa asignatura se consideran del profesor, pero no afecta a otras asignaturas.

> En grupos donde las publicaciones van firmadas con un nombre (por ejemplo “Coordinación del grado”), se usa esa firma. En grupos normales se usa el usuario de Telegram.

---

## 10. Dónde se guardan tus archivos

Por defecto, junto al proyecto:

```
Student-Companion/
├── data/                      # privado: credenciales, sesión, índice y registro
│   ├── config.json
│   ├── student_support.db
│   ├── telegram.session
│   └── student_support.log
└── Descargas Telegram/
    ├── Matemáticas II/
    │   ├── Grupo de teoría/
    │   │   └── 2026-09-14_10-35_1234_Apuntes tema 1.pdf
    │   └── Grupo de prácticas/
    └── Física/
```

Los archivos se llaman `AAAA-MM-DD_HH-MM_idmensaje_nombreoriginal.ext`, así que se ordenan por fecha y no se sobrescriben.

Puedes cambiar la carpeta desde **Archivo → Cambiar carpeta de descargas…**. Los archivos ya bajados no se mueven; las descargas nuevas irán a la nueva carpeta.

---

## 11. Mantenerlo actualizado

Si clonaste el repositorio, actualiza sin perder tus datos:

```powershell
git pull
pip install -r requirements.txt
python main.py
```

`git pull` solo cambia el código: tus carpetas `data/` y `Descargas Telegram/` están excluidas del repositorio y no se tocan. Si descargaste un ZIP, descomprime la versión nueva en otra carpeta y copia solamente el código, manteniendo tu `data/` y tus descargas.

---

## 12. Privacidad y buenas prácticas

- **No subas nunca** `data/config.json` (contiene tu `api_hash` y teléfono), `data/telegram.session` (tu sesión), `data/student_support.db` (lo que has leído) ni la carpeta `Descargas Telegram`. Ya están en `.gitignore`, pero ten cuidado si haces capturas o comprimes la carpeta.
- Usa la aplicación **solo con tus propios grupos** y para estudio personal.
- Respeta las normas del canal, los derechos de autor de los apuntes y las condiciones de uso de Telegram. No redistribuyas el material sin permiso.
- La app **solo lee**: no envía mensajes, no se une a grupos ni modifica nada en Telegram.
- Si dejas de usarla, cierra la sesión desde **Telegram → Cerrar sesión de Telegram** y, si quieres, elimina la carpeta `data/`.

---

## 13. Solución de problemas

**El canal o grupo no aparece al buscar**
- Prueba con el nombre oficial completo, el `@usuario` exacto o un enlace `t.me`.
- Comprueba que tu cuenta es miembro del grupo.
- La búsqueda local ve tus chats; la global no siempre indexa grupos privados.

**No llega el código de verificación**
- Telegram lo envía al chat de “Telegram” en la app, no siempre por SMS.
- Revisa también la sesión de escritorio y espera un minuto antes de pedir otro.

**«La sesión guardada ya no es válida»**
- Usa **Telegram → Cerrar sesión de Telegram** y vuelve a conectarte.

**Telegram dice “FloodWait” o va muy lento**
- Es un límite de velocidad de Telegram. La app espera y continúa; si no, puedes cancelar y reintentar más tarde.

**Un archivo no se abre**
- Si lo borraste o moviste, sincroniza la asignatura: la app lo detecta y lo descarga otra vez.
- También puedes usar **Abrir carpeta** para localizarlo.

**Error al iniciar**
- Lee `data/student_support.log`. Si no sabes qué significa, copia las últimas líneas (sin incluir credenciales) al abrir un issue.

**La interfaz se ve pequeña o recortada**
- Ajusta el escalado de Windows o usa una resolución de al menos 1280×800.

---

## 14. Preguntas frecuentes

**¿Tengo que dejar la aplicación abierta para recibir lo nuevo?**
No. Sincroniza cuando quieras; ella consulta solo lo que falta desde la última vez.

**¿Puedo usar varios grupos para la misma asignatura?**
Sí. Al crearla o desde **Añadir**, selecciona todos los grupos que quieras.

**¿Puedo usarla en macOS o Linux?**
El código de Telethon es multiplataforma, pero la interfaz y las pruebas están pensadas para Windows. En otros sistemas puede funcionar, pero no está garantizado.

**¿Se descargan chats privados con personas?**
No. Está pensada para canales y grupos, no para conversaciones uno a uno.

**¿Qué pasa si quito un canal o elimino una asignatura?**
Se borra el índice de la base de datos, pero **no** los archivos que ya descargaste.

**¿Puedo cambiar el idioma?**
La interfaz está en español. Los nombres de tus asignaturas y grupos pueden ser en cualquier idioma.

---

¿Encontraste un error o falta una explicación? Abre un issue en <https://github.com/AxAvier7/Student-Companion/issues> indicando tu sistema operativo, versión de Python y los pasos para reproducirlo.
