# PROYECTO: FROSTBASE

## Sistema web de monitoreo de camiones refrigerados

Actúa como un desarrollador Full Stack Senior y arquitecto de software. Tu objetivo es desarrollar una aplicación web funcional, completa, mantenible y preparada para producción llamada **FrostBase**.

No quiero únicamente un prototipo visual. Necesito que implementes el frontend, backend, base de datos, API REST, simulador IoT y todas las funcionalidades descritas.

Prioriza:

- Código limpio, modular y mantenible.
- Interfaz minimalista y profesional.
- Seguridad en la comunicación entre dispositivos y servidor.
- Arquitectura preparada para incorporar dispositivos ESP32-S3 reales.
- Experiencia de usuario fluida, sin recargas completas de página.
- Documentación suficiente para instalar, ejecutar y modificar el proyecto.

---

# 1. IDENTIDAD VISUAL Y DISEÑO

La aplicación se llama FrostBase y está dedicada al monitoreo de camiones refrigerados.

Quiero una estética que combine:

- Tecnología y monitoreo industrial.
- Ambientes fríos, hielo y refrigeración.
- Diseño moderno, minimalista y profesional.

## Paleta de colores

Utiliza estos colores como base del sistema de diseño:

| Nombre         | Código  |
| -------------- | ------- |
| Azul principal | #033E8C |
| Azul eléctrico | #2F7BFF |
| Crema hielo    | #F9ECE5 |
| Azul hielo     | #8A9BD6 |
| Azul noche     | #0B1426 |

Colores para estados:

| Estado              | Código  |
| ------------------- | ------- |
| Correcto / En línea | #27C6A3 |
| Advertencia         | #FFBE55 |
| Crítico / Alerta    | #F05B65 |
| Desconectado        | #718096 |

## Distribución visual

Utiliza como referencia principal el diseño del archivo "panel de control.jpg" que se encuentra en esta carpeta.

Características que debes conservar:

- Barra lateral vertical azul oscuro.
- Logotipo y nombre FrostBase en la parte superior.
- Elementos de navegación con iconos Font Awesome.
- Opción seleccionada con fondo azul eléctrico.
- Área principal con fondo crema.
- Tarjetas KPI compactas, con esquinas redondeadas.
- Mapa de ubicación en tiempo real como elemento principal.
- Gráficas e indicadores visualmente discretos.
- Tipografía moderna y legible.
- Espaciado consistente y diseño minimalista.

No satures la interfaz con degradados, sombras, bordes o animaciones innecesarias.

## Logo y favicon

No diseñes ni generes un logotipo nuevo.

Deja preparados los siguientes archivos:

- Frontend: `assets/logo.png`
- Favicon: `assets/logo.png`

El logo debe aparecer en la barra lateral junto al nombre FrostBase.

Si los archivos todavía no existen, utiliza un espacio reservado y evita errores visuales. No reemplaces el logo por un icono inventado.

## Modo oscuro y claro

Implementa ambos temas.

- El modo claro debe utilizar el color crema como fondo de las tarjetas y superficies.
- El modo oscuro debe utilizar azul noche como fondo principal.
- Los colores de identidad deben conservarse en ambos modos.
- Guardar la preferencia del administrador para mantenerla entre sesiones.

Utiliza variables CSS para centralizar los colores y facilitar modificaciones posteriores.

---

# 2. ARQUITECTURA DEL PROYECTO

Utiliza una arquitectura modular.

## Backend

- Python 3.12 o superior.
- FastAPI.
- PostgreSQL.
- SQLAlchemy 2.
- Alembic para migraciones.
- Pydantic para validación.
- JWT para autenticación.
- Passlib o pwdlib con Argon2 para contraseñas.
- Uvicorn para ejecutar el servidor.

Organiza el backend separando:

- Configuración.
- Conexión a base de datos.
- Modelos.
- Esquemas de validación.
- Repositorios o acceso a datos.
- Servicios y lógica de negocio.
- Controladores / endpoints.
- Autenticación y autorización.
- Integración con servicios externos.

Utiliza variables de entorno mediante `.env`.

No coloques credenciales directamente en el código.

## Frontend

Utiliza exclusivamente:

- HTML5.
- CSS3.
- JavaScript vanilla.
- Font Awesome para iconos.
- Leaflet para mapas.

No utilizar React, Vue, Angular, Astro ni otros frameworks frontend.

Cada pantalla debe tener su propio archivo HTML y su propio módulo JavaScript cuando corresponda.

Centraliza los estilos compartidos en archivos CSS reutilizables.

No construyas toda la aplicación en un único HTML ni concentres toda la lógica en un solo archivo JavaScript.

## Estructura sugerida

Organiza el proyecto de forma similar a la siguiente:

```text
FrostBase/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── database.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   ├── api/
│   │   │   └── v1/
│   │   └── utils/
│   ├── alembic/
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── assets/
│   │   └── logo.png
│   ├── css/
│   │   ├── variables.css
│   │   ├── global.css
│   │   ├── components.css
│   │   ├── layout.css
│   │   └── pages/
│   ├── js/
│   │   ├── core/
│   │   │   ├── api.js
│   │   │   ├── auth.js
│   │   │   ├── notifications.js
│   │   │   └── theme.js
│   │   ├── components/
│   │   └── pages/
│   ├── login.html
│   ├── dashboard.html
│   ├── trucks.html
│   ├── truck-detail.html
│   ├── routes.html
│   ├── route-detail.html
│   ├── alerts.html
│   └── settings.html
│
├── iot-simulator/
│   ├── simulator.py
│   ├── requirements.txt
│   └── .env.example
│
├── docs/
│   ├── API.md
│   ├── DATABASE.md
│   ├── IOT-INTEGRATION.md
│   └── INSTALLATION.md
│
├── docker-compose.yml
├── .gitignore
└── README.md
```

Puedes modificar la estructura si encuentras una organización técnicamente mejor, pero conserva la separación de responsabilidades y de pantallas.

---

# 3. BASE DE DATOS POSTGRESQL

Diseña una base de datos relacional normalizada.

Como mínimo, contempla las siguientes entidades:

## Administradores

- ID.
- Nombre de usuario.
- Correo electrónico.
- Contraseña cifrada mediante hash.
- Fecha de creación.
- Último acceso.

Por el momento solo existirá un administrador.

No implementar registro público de usuarios.

Crear un mecanismo de inicialización que permita generar el administrador inicial mediante variables de entorno.

## Camiones

Cada camión debe tener:

- ID único.
- Marca.
- Modelo.
- Año.
- Placas.
- Descripción opcional.
- Estado operativo.
- Ruta asignada.
- Dispositivo IoT asociado.
- Fecha de registro.
- Última comunicación del dispositivo.

Estados posibles:

- En ruta.
- Fuera de ruta / Disponible.
- Mantenimiento.

El ID del camión será la referencia para relacionar las lecturas del dispositivo IoT.

No utilizar las placas como identificador principal.

## Dispositivos IoT

Cada dispositivo debe tener:

- ID único.
- Identificador físico del ESP32-S3.
- Camión asociado.
- Clave de autenticación almacenada de forma segura.
- Estado de conexión.
- Fecha de última comunicación.
- Fecha de registro.

Un dispositivo solamente puede estar asociado a un camión a la vez.

La relación debe poder modificarse desde el sistema.

## Rutas

Cada ruta debe contener:

- ID.
- Nombre.
- Descripción opcional.
- Lista ordenada de puntos de entrega.
- Coordenadas geográficas de cada punto.
- Geometría de la ruta calculada.
- Estado.
- Fecha de creación.

El nombre se generará automáticamente utilizando el primer y último punto.

Ejemplo:

`Villa Fontana - Centro`

Permitir que una ruta tenga varios puntos de entrega intermedios.

Guardar la geometría de la ruta para poder representarla posteriormente en Leaflet.

## Lecturas IoT

Cada lectura debe almacenar:

- ID.
- Dispositivo asociado.
- Camión asociado.
- Temperatura en °C.
- Humedad relativa en porcentaje.
- Latitud.
- Longitud.
- Fecha y hora de recepción.
- Fecha y hora de la lectura del dispositivo.

Las lecturas deben conservar un historial.

Utilizar UTC para almacenar las fechas en la base de datos.

Permitir consultar las lecturas por camión y rango de fechas.

Considerar índices para optimizar consultas históricas.

## Alertas

Cada alerta debe contener:

- ID.
- Camión.
- Dispositivo.
- Tipo de alerta.
- Valor registrado.
- Valor mínimo permitido.
- Valor máximo permitido.
- Fecha de inicio.
- Fecha de resolución.
- Estado.

Tipos iniciales:

- Temperatura fuera de rango.
- Humedad fuera de rango.
- Dispositivo desconectado.

Estados:

- Activa.
- Resuelta.

Evitar generar una alerta nueva en cada lectura cuando una condición anormal continúa. Mantener una alerta activa hasta que la condición se normalice.

## Configuración

Almacenar los rangos de temperatura y humedad en la base de datos.

Valores iniciales:

Temperatura:

- Ideal: -2 °C.
- Variación permitida: ±3 °C.
- Mínimo: -5 °C.
- Máximo: 1 °C.

Humedad:

- Ideal: 80%.
- Variación permitida: ±5%.
- Mínimo: 75%.
- Máximo: 85%.

Los límites deben ser configurables desde el frontend.

La validación debe realizarse en el backend, no únicamente en JavaScript.

---

# 4. AUTENTICACIÓN

Implementa un login para el administrador.

Características:

- Inicio de sesión mediante usuario/correo y contraseña.
- JWT para gestionar sesiones.
- Contraseñas almacenadas con hash seguro.
- Protección de todas las pantallas internas.
- Cierre de sesión.
- Redirección al login cuando no exista una sesión válida.
- Mensajes toast para errores de autenticación.

Utiliza cookies HttpOnly y Secure en producción para proteger el token, con una política SameSite apropiada.

No guardar contraseñas ni claves de dispositivos en el frontend.

No permitir que los endpoints administrativos sean utilizados sin autenticación.

---

# 5. DASHBOARD / PANTALLA DE INICIO

Esta es la pantalla más importante de la aplicación.

Debe reproducir lo más fielmente posible la distribución del primer panel de FrostBase generado como referencia.

## Barra lateral

Opciones:

1. Inicio.
2. Flota.
3. Rutas.
4. Historial de alertas.
5. Configuración.

En la parte inferior:

- Selector de tema claro/oscuro.
- Cerrar sesión.

Utilizar Font Awesome.

## Indicadores KPI

Colocar tres tarjetas compactas en la parte superior:

### KPI 1: Camiones activos

Mostrar la cantidad de camiones que actualmente están en ruta.

Ejemplo: 12 camiones activos.

### KPI 2: Temperatura promedio

Mostrar la temperatura promedio de los camiones que tengan lecturas recientes.

No incluir camiones sin lecturas válidas.

### KPI 3: Efectividad

Mostrar un porcentaje de efectividad del sistema.

Como definición inicial, calcular:

Porcentaje de lecturas dentro de los rangos permitidos / total de lecturas válidas del periodo × 100.

Utilizar las lecturas de las últimas 24 horas.

Evitar utilizar valores ficticios o porcentajes estáticos.

## Carrusel de temperaturas

Incorporar un carrusel compacto de temperaturas individuales.

Cada elemento debe mostrar:

- Nombre o placas del camión.
- Temperatura actual.
- Humedad actual.
- Estado de la lectura.
- Indicador visual de normalidad o alerta.

Los camiones deben poder recorrerse mediante controles del carrusel.

## Mapa en tiempo real

Utilizar Leaflet y OpenStreetMap.

El mapa debe mostrar:

- Ubicación GPS de cada camión.
- Marcadores grises cuando el camión no esté en ruta.
- Marcadores azules cuando el camión esté en ruta.
- Nombre o placas al seleccionar un marcador.
- Temperatura y humedad actuales en el popup.
- Última actualización recibida.

También debe mostrar la ruta asignada al camión.

Dibujar la geometría de la ruta mediante una polilínea.

Si se selecciona un camión, destacar su ruta y su marcador.

Permitir visualizar todos los camiones o filtrar uno específico.

Utilizar atribución correcta de OpenStreetMap.

No inventar ubicaciones si el dispositivo no ha enviado coordenadas.

## Panel de alertas / Estado general

En el espacio donde originalmente existía el gráfico circular, implementar un panel de estado general.

Cuando todos los camiones estén dentro de los rangos:

- Mostrar una carita feliz.
- Mostrar el texto "Todo bien".
- Utilizar color gris o un verde discreto.
- No llamar demasiado la atención.

Cuando existan anomalías:

- Cambiar la carita feliz por un icono de fuego.
- Utilizar rojo para destacar la alerta.
- Mostrar el nombre o placas del camión afectado.
- Indicar el problema detectado.
- Mostrar el valor registrado y el rango permitido.

Si existe más de un camión con problemas, mostrar las alertas mediante un carrusel.

Al seleccionar una alerta, permitir acceder al detalle del camión.

## Clima de Tijuana

Incorporar una tarjeta discreta que muestre:

- Temperatura actual de Tijuana.
- Condición climática.
- Icono del clima.
- Hora de última actualización.

Utilizar Open-Meteo como primera opción, sin necesidad de API Key.

Coordenadas iniciales de Tijuana:

- Latitud: 32.5149.
- Longitud: -117.0382.

Configurar la ciudad y coordenadas para que puedan modificarse posteriormente.

Diferenciar claramente la temperatura ambiental de la temperatura de los camiones.

Implementar caché para evitar consultas innecesarias al servicio externo.

## Actualización automática

El dashboard debe actualizar sus datos cada 10 segundos.

IMPORTANTE:

No recargar la página completa.

Utilizar JavaScript con Fetch API y actualizar solamente los componentes afectados.

Evitar que:

- El mapa se reinicialice cada 10 segundos.
- Los carruseles regresen al primer elemento.
- Se pierda la selección del usuario.
- Se generen solicitudes duplicadas.
- Se acumulen temporizadores al navegar.

Mantener una instancia permanente del mapa y actualizar los marcadores y polilíneas.

Mostrar un pequeño indicador de última actualización.

Si falla la conexión, mostrar un aviso discreto sin borrar los últimos datos válidos.

---

# 6. GESTIÓN DE CAMIONES (CRUD)

Crear una pantalla independiente para administrar la flota.

Funciones:

- Listar camiones.
- Registrar camiones.
- Editar información.
- Consultar detalles.
- Eliminar camiones cuando sea seguro hacerlo.
- Buscar por placas, marca o modelo.
- Filtrar por estado.
- Asignar o modificar rutas.
- Asociar dispositivos IoT.

La tabla debe mostrar:

- Placas.
- Marca y modelo.
- Estado.
- Ruta asignada.
- Temperatura actual.
- Humedad actual.
- Última comunicación.

Crear una pantalla de detalle para cada camión.

Esta pantalla debe incluir:

- Información general.
- Estado del dispositivo.
- Temperatura actual.
- Humedad actual.
- Ubicación GPS.
- Mapa.
- Ruta asignada.
- Historial de lecturas.
- Historial de alertas.

Utilizar confirmaciones antes de eliminar registros.

No eliminar automáticamente el historial histórico de lecturas o alertas al eliminar o desasociar un camión. Implementar eliminación lógica o restricciones de integridad según corresponda.

---

# 7. GESTIÓN DE RUTAS

Crear una pantalla para administrar rutas.

El administrador debe poder:

1. Crear una ruta.
2. Agregar puntos de entrega.
3. Ordenar los puntos de entrega.
4. Consultar los puntos sobre un mapa.
5. Calcular la ruta.
6. Guardar la ruta.
7. Asignar la ruta a un camión.
8. Modificar una ruta existente.

Cada punto debe tener:

- Nombre.
- Dirección o descripción.
- Latitud.
- Longitud.
- Orden de visita.

Permitir seleccionar ubicaciones directamente en el mapa y guardar sus coordenadas.

Para calcular las rutas, utilizar OSRM como proveedor inicial.

Guardar la geometría calculada en la base de datos para evitar recalcularla en cada consulta.

Mantener el proveedor de rutas configurable para poder sustituirlo posteriormente.

Si el servicio de rutas no está disponible, informar al usuario mediante toast y no guardar una geometría incorrecta.

El nombre de la ruta debe generarse automáticamente:

`Primer punto - Último punto`

Ejemplo:

`Villa Fontana - Centro`

Una ruta puede asignarse a un solo camión a la vez en esta primera versión.

---

# 8. HISTORIAL DE ALERTAS

Crear una pantalla independiente.

Mostrar una tabla con:

- Fecha y hora.
- Camión.
- Tipo de alerta.
- Valor detectado.
- Rango permitido.
- Estado.

Filtros:

- Camión.
- Tipo de alerta.
- Activa / Resuelta.
- Fecha inicial y final.

Permitir consultar los detalles de cada alerta.

Las alertas deben generarse automáticamente cuando las lecturas superen los rangos establecidos.

Cuando las lecturas vuelvan a estar dentro de los límites, marcar la alerta como resuelta.

No borrar el historial de alertas resueltas.

---

# 9. CONFIGURACIÓN DE RANGOS

Crear una pantalla para configurar los parámetros ambientales.

Temperatura:

- Temperatura ideal: -2 °C.
- Tolerancia: ±3 °C.

Humedad:

- Humedad ideal: 80%.
- Tolerancia: ±5%.

Mostrar los límites calculados.

Ejemplo:

Temperatura permitida: -5 °C a 1 °C.

Humedad permitida: 75% a 85%.

Permitir modificar los valores desde formularios.

Validar los valores antes de guardarlos.

Solicitar confirmación antes de aplicar cambios.

Los cambios deben reflejarse inmediatamente en las validaciones posteriores del backend.

---

# 10. API REST PARA ESP32-S3

La API debe estar preparada para recibir información de dispositivos físicos, aunque inicialmente se utilice un simulador.

Implementar una API versionada:

`/api/v1/`

## Recepción de lecturas

Crear un endpoint:

`POST /api/v1/iot/readings`

El dispositivo enviará:

- Identificador del dispositivo.
- Temperatura.
- Humedad.
- Latitud.
- Longitud.
- Timestamp de la lectura.

Ejemplo de payload:

```json
{
  "device_id": "ESP32-FROST-001",
  "temperature": -2.4,
  "humidity": 79.5,
  "latitude": 32.5149,
  "longitude": -117.0382,
  "timestamp": "2026-11-15T22:30:00Z"
}
```

La autenticación debe realizarse mediante una clave individual del dispositivo, por ejemplo, mediante el encabezado:

`X-Device-Key: <device_secret>`

Requisitos:

- Validar que el dispositivo exista.
- Validar su clave.
- Identificar automáticamente el camión asociado.
- Validar los rangos físicos de los datos.
- Rechazar coordenadas inválidas.
- Registrar la lectura en PostgreSQL.
- Actualizar la última comunicación del dispositivo.
- Evaluar las condiciones de alerta.
- Devolver una respuesta JSON con el resultado.

Nunca confiar en que el dispositivo indique libremente a qué camión pertenece. La asociación debe obtenerse de la base de datos.

Utilizar HTTPS en producción.

## Respuesta de ejemplo

```json
{
  "success": true,
  "message": "Lectura registrada correctamente",
  "truck_id": 1,
  "alerts": []
}
```

## Consideraciones de integración

Diseñar el endpoint para que un ESP32-S3 pueda enviar datos fácilmente utilizando `HTTPClient` o una biblioteca HTTP equivalente.

No exigir que el ESP32 utilice JWT de administrador.

Separar completamente la autenticación administrativa de la autenticación IoT.

Documentar el formato de envío, autenticación, respuestas y códigos HTTP.

---

# 11. SIMULADOR IoT

Crear un script independiente:

`iot-simulator/simulator.py`

Este script simulará un dispositivo ESP32-S3.

Debe poder ejecutarse independientemente del frontend y del servidor web.

## Funcionamiento

- Simular un único dispositivo.
- Asociarlo a un camión existente.
- Enviar una lectura cada 10 segundos.
- Utilizar la API real de FrostBase.
- Autenticarse mediante la clave del dispositivo.
- Generar temperatura, humedad y GPS.

## Comportamiento de las lecturas

Las lecturas deben ser estables.

Valores normales aproximados:

- Temperatura: alrededor de -2 °C.
- Humedad: alrededor de 80%.

Agregar pequeñas variaciones naturales para evitar que todas las lecturas sean idénticas.

Ejemplos:

- Temperatura: -2.1, -1.8, -2.3.
- Humedad: 79.4, 80.2, 81.1.

## Probabilidad de anomalías

Cada lectura tendrá una probabilidad independiente del 1% de presentar una anomalía fuera de los rangos configurados.

El 99% restante deberá mantenerse dentro de los rangos normales.

Cuando ocurra una anomalía:

- Generar una temperatura o humedad fuera del rango permitido.
- Registrar el envío en la consola.
- Permitir que el backend genere la alerta correspondiente.

Las anomalías no deben ser permanentes: las siguientes lecturas normalmente volverán a valores estables.

El simulador debe utilizar los rangos configurados en el sistema cuando sea posible, o permitir configurarlos mediante variables de entorno.

## GPS

Simular el desplazamiento del camión sobre la ruta asignada.

Si el camión tiene una ruta:

- Obtener su geometría.
- Recorrer sus coordenadas progresivamente.
- Enviar nuevas coordenadas cada 10 segundos.
- Mantener el movimiento dentro de la ruta.

Si no tiene una ruta, utilizar una ubicación fija configurable de Tijuana.

## Consola

Mostrar información como:

```text
[FROSTBASE SIMULATOR]
Device: ESP32-FROST-001
Truck: ABC-123-A
Temperature: -2.1 °C
Humidity: 80.4 %
GPS: 32.5149, -117.0382
Status: NORMAL
Sending next reading in 10 seconds...
```

Cuando ocurra una anomalía, indicarlo claramente.

Agregar manejo de errores, reconexión y tolerancia a fallos temporales del servidor.

No detener permanentemente el simulador por un error de conexión.

---

# 12. CONECTIVIDAD Y ACTUALIZACIÓN DE DISPOSITIVOS

Implementar un mecanismo para determinar si un dispositivo está conectado.

Utilizar `last_seen` y un tiempo configurable de expiración.

Por ejemplo:

- Recibió una lectura recientemente: En línea.
- No ha recibido lecturas durante el tiempo establecido: Desconectado.

No confundir el estado del dispositivo con el estado operativo del camión.

Un camión puede estar disponible mientras su dispositivo está conectado.

Mostrar el estado de ambos elementos por separado.

Crear una alerta de dispositivo desconectado cuando corresponda, evitando duplicados.

---

# 13. NOTIFICACIONES TOAST

Implementar notificaciones toast para:

- Operaciones exitosas.
- Errores.
- Advertencias.
- Información.
- Cambios de configuración.
- Registro y edición de camiones.
- Creación y modificación de rutas.
- Problemas de conexión.
- Alertas relevantes.

Utilizar una librería ligera como Toastify.js o equivalente.

Mantener un diseño visual coherente con FrostBase.

No utilizar ventanas `alert()` o `confirm()` nativas como sistema principal de notificaciones.

Para operaciones destructivas, utilizar diálogos de confirmación personalizados.

---

# 14. API ADMINISTRATIVA

Organizar los endpoints bajo `/api/v1/`.

Contemplar como mínimo:

**Autenticación**

- POST `/auth/login`
- POST `/auth/logout`
- GET `/auth/me`

**Dashboard**

- GET `/dashboard/summary`
- GET `/dashboard/trucks`
- GET `/dashboard/alerts`
- GET `/dashboard/weather`

**Camiones**

- GET `/trucks`
- POST `/trucks`
- GET `/trucks/{id}`
- PUT `/trucks/{id}`
- DELETE `/trucks/{id}`

**Dispositivos**

- GET `/devices`
- POST `/devices`
- GET `/devices/{id}`
- PUT `/devices/{id}`
- POST `/devices/{id}/rotate-key`

**Rutas**

- GET `/routes`
- POST `/routes`
- GET `/routes/{id}`
- PUT `/routes/{id}`
- DELETE `/routes/{id}`
- POST `/routes/{id}/calculate`

**Lecturas**

- GET `/readings`
- GET `/readings/truck/{truck_id}`

**Alertas**

- GET `/alerts`
- GET `/alerts/{id}`

**Configuración**

- GET `/settings`
- PUT `/settings`

Todos los endpoints administrativos deben requerir autenticación.

Los endpoints IoT deben utilizar autenticación específica de dispositivo.

Incluir paginación y filtros en los endpoints que devuelvan grandes cantidades de información.

Utilizar códigos HTTP adecuados y respuestas consistentes.

---

# 15. EXPERIENCIA DE USUARIO Y RESPONSIVIDAD

La aplicación debe funcionar correctamente en:

- Computadoras de escritorio.
- Laptops.
- Tablets.
- Teléfonos móviles.

La versión de escritorio es la prioridad.

En dispositivos pequeños:

- Convertir la barra lateral en menú desplegable.
- Adaptar las tarjetas KPI.
- Mantener el mapa funcional.
- Evitar desbordamientos horizontales.
- Adaptar las tablas.

Mantener transiciones discretas.

Utilizar estados de carga, indicadores vacíos y mensajes de error comprensibles.

No mostrar información inventada para rellenar espacios vacíos.

---

# 16. DOCKER Y EJECUCIÓN

Preparar Docker Compose para facilitar el despliegue local.

Como mínimo, incluir:

- PostgreSQL.
- Backend FastAPI.

El frontend puede servirse mediante FastAPI durante el desarrollo, manteniendo los archivos separados.

Preparar los servicios para que puedan ejecutarse mediante un solo comando.

Incluir:

- Variables de entorno.
- Inicialización de base de datos.
- Migraciones Alembic.
- Creación del administrador inicial.
- Documentación de instalación.

No incluir contraseñas reales en el repositorio.

---

# 17. DOCUMENTACIÓN

Crear un README.md que explique:

1. Qué es FrostBase.
2. Tecnologías utilizadas.
3. Estructura del proyecto.
4. Requisitos de instalación.
5. Configuración del archivo `.env`.
6. Cómo iniciar PostgreSQL y FastAPI.
7. Cómo aplicar migraciones.
8. Cómo iniciar el frontend.
9. Cómo iniciar el simulador IoT.
10. Cómo registrar un nuevo dispositivo.
11. Cómo vincular un dispositivo a un camión.
12. Cómo probar la recepción de lecturas.
13. Cómo acceder a la documentación Swagger de FastAPI.

Crear también documentación específica de integración para el ESP32-S3.

---

# 18. CRITERIOS DE ACEPTACIÓN

El proyecto no se considerará terminado hasta que se cumplan estos puntos:

- [ ] El administrador puede iniciar y cerrar sesión.
- [ ] PostgreSQL almacena correctamente los datos.
- [ ] Se pueden registrar, editar y consultar camiones.
- [ ] Se pueden crear rutas con múltiples puntos.
- [ ] Las rutas se pueden asignar a camiones.
- [ ] El mapa representa correctamente los camiones y sus rutas.
- [ ] Se pueden registrar dispositivos IoT.
- [ ] Cada dispositivo puede autenticarse individualmente.
- [ ] La API recibe y almacena lecturas.
- [ ] El simulador envía datos cada 10 segundos.
- [ ] Las lecturas se reflejan en el dashboard sin recargar la página.
- [ ] Las anomalías generan alertas.
- [ ] Las alertas se resuelven cuando los valores vuelven a la normalidad.
- [ ] Se puede consultar el historial de alertas.
- [ ] Se pueden modificar los rangos ambientales.
- [ ] Se muestra el clima de Tijuana.
- [ ] Funcionan los modos oscuro y claro.
- [ ] Las notificaciones toast funcionan correctamente.
- [ ] El sistema funciona de manera responsiva.
- [ ] La documentación permite instalar y ejecutar el proyecto desde cero.

---

# 19. INSTRUCCIONES FINALES DE DESARROLLO

Sigue este orden de trabajo:

**Fase 1: Arquitectura**

- Crear la estructura del proyecto.
- Configurar PostgreSQL.
- Crear los modelos y relaciones.
- Configurar Alembic.
- Preparar Docker Compose.

**Fase 2: Backend**

- Implementar autenticación.
- Implementar CRUD.
- Implementar rutas.
- Implementar dispositivos IoT.
- Implementar recepción de lecturas.
- Implementar sistema de alertas.
- Implementar dashboard y clima.

**Fase 3: Frontend**

- Crear el sistema de diseño.
- Implementar login.
- Crear barra lateral.
- Crear dashboard.
- Crear gestión de camiones.
- Crear gestión de rutas.
- Crear historial de alertas.
- Crear configuración.
- Implementar modo oscuro y claro.

**Fase 4: IoT**

- Crear el simulador.
- Probar la comunicación con FastAPI.
- Verificar el almacenamiento de lecturas.
- Verificar el comportamiento de alertas.

**Fase 5: Integración y pruebas**

- Conectar todos los componentes.
- Verificar actualizaciones cada 10 segundos.
- Probar las rutas y los mapas.
- Probar los diferentes estados de los camiones.
- Corregir errores.
- Verificar todos los criterios de aceptación.

## Reglas importantes

1. No omitas funcionalidades para terminar más rápido.
2. No sustituyas funcionalidades reales por datos estáticos o botones decorativos.
3. No concentres toda la aplicación en pocos archivos.
4. No generes datos ficticios en producción.
5. Utiliza datos de prueba únicamente mediante un mecanismo de seed claramente identificado.
6. Implementa validaciones tanto en frontend como en backend.
7. Mantén el código preparado para agregar más dispositivos ESP32-S3 en el futuro.
8. No hardcodees credenciales, claves API ni secretos.
9. Si un servicio externo falla, la aplicación debe informar el problema sin bloquear las demás funcionalidades.
10. Ejecuta pruebas y corrige los errores que encuentres antes de considerar terminado el proyecto.

**Resultado esperado:** un proyecto completo de FrostBase, ejecutable localmente, con PostgreSQL, FastAPI, frontend independiente, simulador IoT y documentación de instalación e integración.

No te limites a describir cómo implementar las funcionalidades. Escribe los archivos, implementa el código y verifica que los componentes se comuniquen correctamente.
