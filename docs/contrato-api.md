# Contrato de entidades y API

Diseño de Fase 1; describe comportamiento por implementar, no una API disponible. Los ejemplos son ilustrativos, no evidencia de ejecución. OpenAPI deberá reflejar este contrato cuando se creen los servicios.

## Convenciones

Las solicitudes y respuestas con cuerpo usan `application/json`. Cada servicio expone las rutas indicadas sin prefijo; el proxy público añade `/api` (por ejemplo, `/api/productos`). No se requiere autenticación en este alcance.

UUID se representa como cadena. Las fechas son ISO 8601 en UTC con zona explícita, por ejemplo `2026-11-03T15:00:00Z`. El servidor genera identificadores y fechas; `updated_at` cambia tras una actualización válida y `created_at` permanece constante.

Importes: admiten tanto números JSON (`float`, `int`, por ejemplo `12.50` o `12`) como cadenas decimales (`"12.50"`), con hasta dos decimales en solicitudes y exactamente dos en respuestas (`"12.50"`). Se rechazan valores con más de dos decimales, valores no positivos o no numéricos; no se redondea silenciosamente. Se normaliza a `Decimal` en Python y se almacena en `NUMERIC` en PostgreSQL, garantizando precisión financiera exacta sin almacenar jamás como `float` en base de datos. La moneda no ha sido definida; la interfaz no debe asumir un símbolo monetario.

Los cuerpos de escritura deben ser objetos JSON. Se rechazan campos desconocidos y campos gestionados por el servidor (`422`). Tipos estrictos: no aceptar cadenas ni booleanos como cantidad, ni cadenas como booleanos. `PATCH` requiere al menos un campo permitido; un objeto vacío devuelve `422`. Un campo omitido conserva su valor. Solo `descripcion` admite `null`; enviarlo elimina la descripción. No se admiten `null` en otros campos.

## Entidades

### Producto

| Campo | Tipo / restricción | Origen |
| --- | --- | --- |
| `id` | UUID | Servidor |
| `nombre` | Cadena, recortada en ambos extremos, entre 1 y 150 caracteres después del recorte; no solo espacios | Cliente |
| `descripcion` | Cadena de hasta 1000 caracteres o `null`; omisión al crear equivale a `null` | Cliente |
| `precio` | Decimal positivo con hasta dos decimales; persistido como `NUMERIC` | Cliente |
| `activo` | Booleano, por defecto `true` al crear | Cliente |
| `created_at`, `updated_at` | Timestamps UTC con zona | Servidor |

No se exige unicidad del nombre. Eliminar un producto es una eliminación física; desactivarlo impide seleccionarlo para nuevos pedidos sin eliminarlo.

### Pedido

| Campo | Tipo / restricción | Origen |
| --- | --- | --- |
| `id` | UUID | Servidor |
| `producto_id` | UUID, referencia lógica a Productos | Cliente, validado por HTTP |
| `producto_nombre` | Copia histórica del nombre seleccionado | Productos |
| `cantidad` | Entero estrictamente positivo | Cliente |
| `precio_unitario` | Copia histórica del precio, `NUMERIC` | Productos |
| `total` | `cantidad × precio_unitario`, `Decimal` / `NUMERIC` | Servidor |
| `created_at`, `updated_at` | Timestamps UTC con zona | Servidor |

Cada pedido contiene un producto y una cantidad. No hay carrito, pagos, autenticación, inventario ni múltiples líneas.

Al crear un pedido, Pedidos consulta `GET /productos/{producto_id}` y verifica existencia, respuesta válida y `activo=true`. El cliente solo puede enviar `producto_id` y `cantidad`; nunca nombre, precio ni total.

Al actualizar únicamente cantidad se conserva nombre y precio históricos, incluso si el producto fue eliminado o desactivado. Si `producto_id` cambia, se consulta el nuevo producto y se toman sus datos actuales; si no se envía cantidad, se conserva la anterior. Enviar el mismo `producto_id` no renueva la copia histórica ni requiere consulta remota. El total siempre se calcula en el servidor.

Modificar o eliminar un producto no altera pedidos previos. Listar, consultar y eliminar pedidos no consulta Productos. Tampoco se consulta Productos al modificar solo cantidad. No existen claves foráneas entre bases ni transacciones distribuidas: la validación refleja el estado del producto en el momento de la consulta.

## Representaciones de respuesta

Producto (`Producto`):

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "nombre": "Pan integral",
  "descripcion": null,
  "precio": "5.50",
  "activo": true,
  "created_at": "2026-11-03T15:00:00Z",
  "updated_at": "2026-11-03T15:00:00Z"
}
```

Pedido (`Pedido`):

```json
{
  "id": "22222222-2222-4222-8222-222222222222",
  "producto_id": "11111111-1111-4111-8111-111111111111",
  "producto_nombre": "Pan integral",
  "cantidad": 3,
  "precio_unitario": "5.50",
  "total": "16.50",
  "created_at": "2026-11-03T15:01:00Z",
  "updated_at": "2026-11-03T15:01:00Z"
}
```

## Endpoints de Productos

| Método y ruta | Solicitud | Éxito y cuerpo | Errores previstos |
| --- | --- | --- | --- |
| `POST /productos` | Obligatorios `nombre`, `precio`; opcionales `descripcion`, `activo` | `201`, `Producto` creado | `422`, `503`, `500` |
| `GET /productos` | Sin cuerpo; `limit`, `offset` opcionales | `200`, página de `Producto` | `422`, `503`, `500` |
| `GET /productos/{id}` | UUID en ruta, sin cuerpo | `200`, `Producto` | `404`, `422`, `503`, `500` |
| `PATCH /productos/{id}` | Uno o más de `nombre`, `descripcion`, `precio`, `activo` | `200`, `Producto` actualizado | `404`, `422`, `503`, `500` |
| `DELETE /productos/{id}` | UUID en ruta, sin cuerpo | `204`, sin cuerpo | `404`, `422`, `503`, `500` |

Ejemplo de creación: `{"nombre":"Pan integral","precio":"5.50"}`. Ejemplo de actualización: `{"descripcion":null,"activo":false}`. La eliminación no comprueba pedidos existentes ni los elimina. Repetir un DELETE de un recurso ya eliminado devuelve `404`.

## Endpoints de Pedidos

| Método y ruta | Solicitud | Éxito y cuerpo | Errores previstos |
| --- | --- | --- | --- |
| `POST /pedidos` | Obligatorios `producto_id`, `cantidad` | `201`, `Pedido` creado | `422`, `503`, `500` |
| `GET /pedidos` | Sin cuerpo; `limit`, `offset` opcionales | `200`, página de `Pedido` | `422`, `503`, `500` |
| `GET /pedidos/{id}` | UUID en ruta, sin cuerpo | `200`, `Pedido` | `404`, `422`, `503`, `500` |
| `PATCH /pedidos/{id}` | Uno o ambos: `producto_id`, `cantidad` | `200`, `Pedido` actualizado | `404`, `422`, `503`, `500` |
| `DELETE /pedidos/{id}` | UUID en ruta, sin cuerpo | `204`, sin cuerpo | `404`, `422`, `503`, `500` |

Ejemplo de creación:

```json
{"producto_id":"11111111-1111-4111-8111-111111111111","cantidad":3}
```

Ejemplo de actualización: `{"cantidad":4}` devuelve precio unitario `"5.50"` y total `"22.00"` para el pedido del ejemplo. Cambiar a otro producto usa su precio actual. Repetir un DELETE de un recurso eliminado devuelve `404`.

## Paginación

En ambos listados, `limit` es entero entre 1 y 100 (predeterminado 20) y `offset` es entero mayor o igual a 0 (predeterminado 0). Valores inválidos devuelven `422`. Orden ascendente por `created_at` y luego `id` para resolver empates. Se incluyen productos activos e inactivos; no se definen filtros adicionales.

La página contiene `items` (representaciones completas), `total` (cantidad total de recursos antes de paginar), `limit` y `offset`. Ejemplo de colección vacía:

```json
{"items":[],"total":0,"limit":20,"offset":0}
```

Un offset fuera del conjunto devuelve `200` con `items: []` y el total real. No se garantiza una instantánea entre solicitudes si hay escrituras concurrentes.

## Salud de cada servicio

| Ruta GET | Verificación | Respuesta |
| --- | --- | --- |
| `/health/live` | Proceso operativo; sin consultas externas | `200`, `{"status":"ok"}` |
| `/health/ready` | Conexión a la base propia con consulta simple | `200`, `{"status":"ready"}`; `503` si no está disponible |

No reciben cuerpo ni parámetros. Readiness de Pedidos no depende de Productos. Estas rutas son internas para operación y probes; no necesitan publicación mediante el proxy.

## Errores

Formato uniforme previsto para validación, dominio y fallos operativos; la implementación debe adaptar también los errores de validación de FastAPI sin devolver el valor recibido ni detalles internos:

```json
{
  "detail": [
    {"loc": ["body", "cantidad"], "code": "invalid_value", "msg": "Debe ser un entero mayor que cero."}
  ]
}
```

`loc` identifica `body`, `path`, `query` o `server`, seguido del campo cuando aplique. `code` permite al frontend decidir el comportamiento; `msg` es un mensaje legible. Puede haber varios errores de validación. No se garantiza prioridad entre errores simultáneos; el frontend no debe depender de ella.

| HTTP | `code` | Situación |
| --- | --- | --- |
| `422` | `invalid_value` | JSON malformado, tipo, longitud, decimal, UUID o paginación inválidos; campo obligatorio ausente o `null` no permitido |
| `422` | `extra_field` | Campo no permitido, incluido precio o total en pedidos |
| `422` | `empty_patch` | PATCH sin campos |
| `422` | `product_not_found` | Productos devuelve `404` durante validación de pedido; `loc: ["body","producto_id"]` |
| `422` | `product_inactive` | Producto válido pero inactivo; misma localización |
| `404` | `not_found` | Producto o pedido solicitado inexistente; `loc: ["path","id"]` |
| `503` | `products_unavailable` | Timeout, fallo de red, respuesta remota distinta de `200`/`404`, JSON o esquema inválido; `loc: ["server"]` |
| `503` | `database_unavailable` | Base propia inaccesible, incluido readiness; `loc: ["server"]` |
| `500` | `internal_error` | Error inesperado; mensaje genérico, `loc: ["server"]` |

Pedidos considera inválida una respuesta remota si no representa un Producto conforme al contrato, incluido un ID distinto del solicitado. El timeout será explícito y configurable mediante `PRODUCTOS_TIMEOUT_SECONDS`, con valor inicial propuesto de 5 segundos; `PRODUCTOS_BASE_URL` identifica el Service interno. No se reintentan escrituras automáticamente. Si falla la validación remota, no se crea ni modifica el pedido. Los fallos de conexión nunca se convierten en producto inexistente ni en `422`.

Los errores nunca exponen trazas, contraseñas, URLs de conexión ni cuerpos remotos. Un fallo al confirmar una escritura puede dejar su resultado incierto para el cliente: no hay garantía de idempotencia para POST; conviene consultar antes de repetirlo.
