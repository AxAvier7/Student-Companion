# Student Support

Repositorio: <https://github.com/AxAvier7/Student-Companion>

Aplicación de escritorio para **recopilar el contenido que publican tus profesores en canales y grupos de Telegram**. Usa [Telethon](https://docs.telethon.dev/) para leer los canales con tu propia cuenta, guarda los archivos en tu ordenador y mantiene un índice en SQLite con el texto, el remitente, la fecha y la ruta de cada archivo.

La interfaz muestra **una pestaña por asignatura**, con la lista de sus canales, una tabla de contenido y un panel de detalle. Al hacer doble clic en un mensaje con archivo, se abre con el programa predeterminado de Windows.

> **¿Eres alumno y quieres usarla con tus propios grupos?** Empieza por la [Guía para estudiantes](GUIA_ESTUDIANTES.md): explica paso a paso cómo obtener las credenciales, encontrar tus grupos, sincronizarlos y organizar los materiales.

---

## Características

- Búsqueda de canales y grupos por nombre, `@usuario` o enlace `t.me`.
- Búsqueda local (tus chats) y global de Telegram, sin distinguir mayúsculas ni tildes.
- Solo se analiza y descarga el contenido **publicado desde el 1 de agosto de 2026**; lo anterior se ignora y se borra.
- Primera sincronización desde esa fecha y solo lo nuevo en las siguientes.
- Registra **quién publicó** cada mensaje y **cuándo**.
- Descarga documentos, PDF, imágenes, vídeos, audios, notas de voz, stickers, etc.
- Índice SQLite con búsqueda por texto, remitente o nombre de archivo.
- Filtro por tipo de contenido: documentos, imágenes, vídeos, audio, texto, enlaces y otros.
- Profesores por asignatura: marca remitentes y filtra solo sus mensajes, combinable con la búsqueda y el tipo.
- Reparación automática: si borras un archivo descargado, la siguiente sincronización lo recupera.
- Apertura de archivos y carpetas con las aplicaciones predeterminadas del sistema.
- Todo funciona sin conexión para consultar lo ya descargado (la sincronización sí necesita internet).

---

## Requisitos

- Windows 10 u 11.
- Python 3.10 o superior (probado con Python 3.13).
- Una cuenta de Telegram.
- Credenciales de API de Telegram (`api_id` y `api_hash`), gratuitas.

---

## Instalación

1. Consigue el código. Puedes clonar el repositorio:

   ```powershell
   git clone https://github.com/AxAvier7/Student-Companion.git
   cd Student-Companion
   ```

   O descargar un ZIP desde <https://github.com/AxAvier7/Student-Companion> y descomprimirlo.

2. Abre una terminal en la carpeta del proyecto e instala la dependencia:

   ```powershell
   pip install -r requirements.txt
   ```

   Si prefieres un entorno virtual:

   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Arranca la aplicación:

   ```powershell
   python main.py
   ```

   También puedes hacer doble clic en **`Iniciar Student Support.bat`**.

---

## Obtener `api_id` y `api_hash`

Telethon necesita identificarse como una aplicación de Telegram:

1. Entra en <https://my.telegram.org> e inicia sesión con tu número de teléfono.
2. Abre **API development tools**.
3. Rellena los datos de la aplicación (por ejemplo: nombre `Student Support`, plataforma `Desktop`, descripción libre).
4. Copia **App api_id** y **App api_hash**.

En la primera pantalla de la aplicación introduce esos dos valores y tu número en formato internacional (por ejemplo `+34600123456`). Telegram te enviará un código a la app de Telegram; escríbelo en el diálogo. Si tienes verificación en dos pasos, también te pedirá la contraseña.

> La sesión se guarda en `data/telegram.session`. Mientras exista, no tendrás que volver a introducir el código. No compartas la carpeta `data/`.

---

## Uso

1. **Inicia sesión** con tus credenciales.
2. Pulsa **Nueva asignatura**, escribe su nombre y busca el canal oficial:
   - por el nombre completo, por ejemplo `Matemáticas II - Grado`;
   - por su `@usuario`;
   - o pegando un enlace `https://t.me/usuario`.
3. Selecciona uno o varios canales/grupos (con `Ctrl` o `Mayús`) y pulsa **Crear asignatura**.
4. Responde que sí a descargar el contenido. La primera sincronización revisa el historial del canal **desde el 1 de agosto de 2026**; lo anterior no se descarga.
5. Navega por las pestañas:
   - la columna izquierda lista los canales y cuántos mensajes tienen;
   - la tabla central muestra fecha, remitente, canal, tipo, texto y archivo;
   - el panel inferior muestra el detalle completo;
   - **doble clic** en un mensaje con archivo lo abre con el programa predeterminado.
6. Usa **Sincronizar** (de una asignatura) o **Sincronizar todo** (`F5`) cuando quieras traer lo nuevo.
7. Para distinguir a los profesores, haz clic derecho sobre uno de sus mensajes y elige **Marcar como profesor**, o abre **Opciones → Profesores…**. Activa la casilla **Solo profesores** para ver únicamente sus mensajes; se combina con la búsqueda y con el filtro de tipo.

### Botones y atajos

| Acción | Dónde |
|---|---|
| Crear asignatura | Botón superior o `Ctrl+N` |
| Sincronizar todo | Botón superior o `F5` |
| Sincronizar una asignatura | Botón **Sincronizar** de su pestaña |
| Añadir o quitar canales | Panel izquierdo de la pestaña |
| Renombrar/eliminar asignatura | Botón **Opciones** de la pestaña |
| Abrir archivo | Doble clic, `Enter` o botón **Abrir archivo** |
| Buscar dentro de una asignatura | Campo **Buscar** |
| Filtrar por tipo | Desplegable **Tipo** (documentos, texto, enlaces…) |
| Marcar profesores | Botón derecho sobre un mensaje o **Opciones → Profesores…** |
| Ver solo profesores | Casilla **Solo profesores** (se combina con el tipo y la búsqueda) |
| Cancelar una sincronización | Botón **Cancelar** de la barra inferior |

---

## Dónde se guarda todo

```
Student Support/
├── data/
│   ├── config.json          # api_id, api_hash, teléfono y carpeta de descargas
│   ├── student_support.db   # índice SQLite (asignaturas, canales y mensajes)
│   ├── telegram.session     # sesión autenticada de Telethon
│   └── student_support.log  # registro de errores y actividad
├── Descargas Telegram/
│   ├── Matemáticas II/
│   │   ├── Grupo de teoría/
│   │   │   └── 2026-09-14_10-35_1234_Apuntes tema 1.pdf
│   │   └── Grupo de prácticas/
│   └── Física/
└── ...
```

Los archivos se nombran con `AAAA-MM-DD_HH-MM_idmensaje_nombreoriginal.ext`, de modo que quedan ordenados y no se repiten.

Puedes cambiar la carpeta de descargas desde **Archivo → Cambiar carpeta de descargas…**. Los archivos ya descargados no se mueven; las nuevas descargas irán a la nueva ubicación.

---

## Cómo funciona por dentro

- `student_support/telegram_service.py` ejecuta Telethon en un hilo aparte con su propio *event loop* de asyncio, para que la interfaz nunca se bloquee.
- `student_support/database.py` guarda asignaturas, canales y mensajes. Se usa `INSERT OR IGNORE` por `(canal, mensaje)` para no duplicar.
- En cada canal se guarda `last_synced_id`; las siguientes sincronizaciones piden solo mensajes con id mayor.
- El límite de fecha está en `student_support/config.py` (`MESSAGE_CUTOFF_LOCAL`). Si lo cambias, se aplica al volver a abrir la app: los mensajes anteriores se borran.
- Antes de descargar lo nuevo se comprueba si falta algún archivo del índice en disco; si falta, se vuelve a pedir ese mensaje concreto y se descarga.
- `student_support/gui/` contiene la interfaz Tkinter/ttk.

---

## Límites y cosas a tener en cuenta

- **Solo se conservan los mensajes publicados desde el 1 de agosto de 2026.** Al abrir la aplicación se borran del índice y del disco los mensajes y archivos anteriores; al sincronizar tampoco se descargan.
- **Debes ser miembro** del canal o grupo para poder leer su historial. La búsqueda global puede mostrar canales públicos a los que no perteneces, pero la descarga fallará hasta que te unas.
- No se descargan chats privados con personas; el programa está pensado para canales y grupos.
- Los enlaces de invitación privados (`t.me/+...`) no se pueden resolver sin unirse. Busca el grupo por su nombre o `@usuario`.
- La primera sincronización de un canal con mucho contenido desde agosto de 2026 puede tardar y ocupar bastante espacio, sobre todo si hay vídeos. Puedes cancelarla en cualquier momento.
- Telegram puede limitar la velocidad de descarga (FloodWait); la app espera y continúa, o muestra el error y sigue con el siguiente canal.
- Los archivos se descargan completos, sin límite de tamaño.
- Al eliminar una asignatura o quitar un canal se borra el índice, pero **no** los archivos del disco.
- Telegram no siempre revela quién administra un canal: si las publicaciones van firmadas, se usa esa firma; si no, aparece el nombre del canal.
- El archivo `data/config.json` contiene tu `api_hash` y `data/telegram.session` tu sesión: trátalos como datos privados y no los subas a repositorios.
- La aplicación solo lee: no envía mensajes, no se une a canales y no modifica nada en Telegram.

---

## Solución de problemas

**No aparece el canal al buscar**
- Prueba con el nombre oficial completo, con el `@usuario` exacto o pegando el enlace `t.me`.
- Comprueba que tu cuenta es miembro del canal/grupo.
- La búsqueda local solo ve los chats de tu cuenta; la global no siempre indexa grupos privados.

**El código no llega**
- Telegram lo envía como mensaje del servicio "Telegram" dentro de la app, no necesariamente por SMS. Revisa también la sesión de escritorio.
- Si ha caducado, inicia sesión de nuevo para pedir otro.

**«La sesión guardada ya no es válida»**
- Usa **Telegram → Cerrar sesión de Telegram** y vuelve a iniciar sesión.

**Un archivo no se abre**
- Si lo borraste o moviste, sincroniza la asignatura: la app detectará que falta y lo descargará de nuevo.
- También puedes abrir la carpeta desde el botón **Abrir carpeta**.

**Errores durante la sincronización**
- Revisa `data/student_support.log`. La app sigue con el resto de canales aunque uno falle.
- Si un canal ya no existe o perdiste el acceso, quítalo de la asignatura.

**La interfaz se ve pequeña o recortada**
- Windows puede estar usando escalado de pantalla. La app es consciente del DPI, pero si usas una escala poco habitual prueba a cambiar el escalado de Windows.

---

## Empaquetar como `.exe` (opcional)

```powershell
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "Student Support" `
  --icon assets\icon.ico --add-data "assets;assets" main.py
```

El ejecutable quedará en `dist\Student Support\`. Los datos se crearán junto al ejecutable.

---

## Aviso

Esta herramienta es para uso personal y académico: recopila contenido al que tu cuenta ya tiene acceso. Respeta las normas de los canales, los derechos de autor de los materiales y las condiciones de uso de Telegram. No la uses para redistribuir contenido sin permiso.
