// ============================================================
// Configuración de URLs
// Con Reverse Proxy en Nginx, todas las peticiones
// se realizan a través de rutas relativas (/api). De este modo,
// el frontend y backend comparten el mismo origen, eliminando
// cualquier restricción de CORS tanto en local como en Kubernetes.
// ============================================================
const PRODUCTOS_URL = "/api";
const PEDIDOS_URL   = "/api";

// ============================================================
// Utilidades
// ============================================================
function formatMoney(value) {
  const num = Number(value);
  if (isNaN(num)) return "Q0.00";
  return "Q" + num.toFixed(2);
}

function formatDate(isoString) {
  if (!isoString) return "—";
  const date = new Date(isoString);
  return date.toLocaleString("es-GT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function showToast(message, type = "success") {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = `toast ${type}`;
  toast.style.display = "block";

  setTimeout(() => {
    toast.style.display = "none";
  }, 3500);
}

function showError(containerId, message) {
  const el = document.getElementById(containerId);
  el.textContent = message;
  el.style.display = "block";
}

function hideError(containerId) {
  const el = document.getElementById(containerId);
  el.style.display = "none";
  el.textContent = "";
}

// ============================================================
// Tabs
// ============================================================
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    // Activar tab
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");

    // Mostrar panel
    const target = tab.dataset.tab;
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    document.getElementById(`panel-${target}`).classList.add("active");

    // Cargar datos del panel
    if (target === "productos") {
      loadProductos();
    } else if (target === "pedidos") {
      loadProductosForSelect();
      loadPedidos();
    }
  });
});

// ============================================================
// PRODUCTOS
// ============================================================
let editingProductoId = null;

async function loadProductos() {
  const tbody = document.getElementById("tbody-productos");
  const loading = document.getElementById("productos-loading");
  const empty = document.getElementById("productos-empty");
  const table = document.getElementById("tabla-productos");

  hideError("productos-error");
  loading.style.display = "block";
  table.style.display = "none";
  empty.style.display = "none";
  tbody.innerHTML = "";

  try {
    const res = await fetch(`${PRODUCTOS_URL}/productos`);
    if (!res.ok) throw new Error(`Error ${res.status}: no se pudo obtener productos`);

    const data = await res.json();
    // Soporta tanto lista directa como {items: [...]}
    const productos = Array.isArray(data) ? data : (data.items || data.productos || []);

    loading.style.display = "none";

    if (productos.length === 0) {
      empty.style.display = "block";
      return;
    }

    table.style.display = "table";

    productos.forEach(p => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>
          <strong>${escapeHtml(p.nombre)}</strong>
          ${p.descripcion ? `<br><small style="color:var(--muted)">${escapeHtml(p.descripcion)}</small>` : ""}
        </td>
        <td>${formatMoney(p.precio)}</td>
        <td>
          <span class="badge ${p.activo ? "badge-active" : "badge-inactive"}">
            ${p.activo ? "Activo" : "Inactivo"}
          </span>
        </td>
        <td>${formatDate(p.created_at)}</td>
        <td>
          <div class="actions">
            <button class="btn btn-sm btn-edit" onclick="startEditProducto('${p.id}')">Editar</button>
            <button class="btn btn-sm btn-danger" onclick="deleteProducto('${p.id}', '${escapeHtml(p.nombre)}')">Eliminar</button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    loading.style.display = "none";
    showError("productos-error", err.message || "No se pudo conectar con el servicio de Productos");
  }
}

function startEditProducto(id) {
  // Buscamos el producto en la tabla actual (o hacemos fetch)
  fetch(`${PRODUCTOS_URL}/productos/${id}`)
    .then(res => {
      if (!res.ok) throw new Error("Producto no encontrado");
      return res.json();
    })
    .then(p => {
      editingProductoId = p.id;
      document.getElementById("producto-id").value = p.id;
      document.getElementById("producto-nombre").value = p.nombre;
      document.getElementById("producto-precio").value = p.precio;
      document.getElementById("producto-descripcion").value = p.descripcion || "";
      document.getElementById("producto-activo").value = p.activo ? "true" : "false";

      document.getElementById("form-producto-title").textContent = "Editar Producto";
      document.getElementById("btn-guardar-producto").textContent = "Actualizar Producto";
      document.getElementById("btn-cancelar-producto").style.display = "inline-flex";

      // Scroll al formulario
      document.getElementById("form-producto").scrollIntoView({ behavior: "smooth" });
    })
    .catch(err => showToast(err.message, "error"));
}

function cancelEditProducto() {
  editingProductoId = null;
  document.getElementById("form-producto").reset();
  document.getElementById("producto-id").value = "";
  document.getElementById("form-producto-title").textContent = "Nuevo Producto";
  document.getElementById("btn-guardar-producto").textContent = "Crear Producto";
  document.getElementById("btn-cancelar-producto").style.display = "none";
}

document.getElementById("btn-cancelar-producto").addEventListener("click", cancelEditProducto);

document.getElementById("form-producto").addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    nombre: document.getElementById("producto-nombre").value.trim(),
    precio: parseFloat(document.getElementById("producto-precio").value),
    descripcion: document.getElementById("producto-descripcion").value.trim() || null,
    activo: document.getElementById("producto-activo").value === "true"
  };

  const btn = document.getElementById("btn-guardar-producto");
  btn.disabled = true;

  try {
    let res;
    if (editingProductoId) {
      // PATCH
      res = await fetch(`${PRODUCTOS_URL}/productos/${editingProductoId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    } else {
      // POST
      res = await fetch(`${PRODUCTOS_URL}/productos`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    }

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const msg = errData.detail || errData.message || `Error ${res.status}`;
      throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    }

    showToast(editingProductoId ? "Producto actualizado" : "Producto creado", "success");
    cancelEditProducto();
    loadProductos();
    // También actualizamos el select de pedidos por si acaso
    loadProductosForSelect();
  } catch (err) {
    showToast(err.message || "Error al guardar producto", "error");
  } finally {
    btn.disabled = false;
  }
});

function detailMessage(errData, status) {
  const d = errData && errData.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) return d.map(e => e.msg || e).join(", ");
  return `Error ${status}`;
}

async function deleteProducto(id, nombre) {
  if (!confirm(`¿Eliminar el producto "${nombre}"?\n\nEsta acción es permanente.`)) return;

  try {
    const res = await fetch(`${PRODUCTOS_URL}/productos/${id}`, {
      method: "DELETE"
    });

    if (!res.ok && res.status !== 204) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(detailMessage(errData, res.status));
    }

    showToast("Producto eliminado", "success");
    loadProductos();
    loadProductosForSelect();
  } catch (err) {
    showToast(err.message || "No se pudo eliminar el producto", "error");
  }
}

document.getElementById("btn-refresh-productos").addEventListener("click", loadProductos);

// ============================================================
// PEDIDOS
// ============================================================
let editingPedidoId = null;

async function loadProductosForSelect() {
  const select = document.getElementById("pedido-producto");
  const currentValue = select.value;

  try {
    const res = await fetch(`${PRODUCTOS_URL}/productos`);
    if (!res.ok) throw new Error("No se pudieron cargar productos");

    const data = await res.json();
    const productos = Array.isArray(data) ? data : (data.items || data.productos || []);

    // Solo productos activos para nuevos pedidos
    const activos = productos.filter(p => p.activo === true);

    select.innerHTML = '<option value="">Seleccione un producto...</option>';

    activos.forEach(p => {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = `${p.nombre} — ${formatMoney(p.precio)}`;
      select.appendChild(opt);
    });

    // Restaurar valor si seguía existiendo
    if (currentValue) select.value = currentValue;
  } catch (err) {
    console.error("Error cargando productos para select:", err);
  }
}

async function loadPedidos() {
  const tbody = document.getElementById("tbody-pedidos");
  const loading = document.getElementById("pedidos-loading");
  const empty = document.getElementById("pedidos-empty");
  const table = document.getElementById("tabla-pedidos");

  hideError("pedidos-error");
  loading.style.display = "block";
  table.style.display = "none";
  empty.style.display = "none";
  tbody.innerHTML = "";

  try {
    const res = await fetch(`${PEDIDOS_URL}/pedidos`);
    if (!res.ok) throw new Error(`Error ${res.status}: no se pudo obtener pedidos`);

    const data = await res.json();
    const pedidos = Array.isArray(data) ? data : (data.items || data.pedidos || []);

    loading.style.display = "none";

    if (pedidos.length === 0) {
      empty.style.display = "block";
      return;
    }

    table.style.display = "table";

    pedidos.forEach(p => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>
          <strong>${escapeHtml(p.producto_nombre)}</strong>
          <br><small style="color:var(--muted)">ID: ${p.producto_id.substring(0, 8)}...</small>
        </td>
        <td>${p.cantidad}</td>
        <td>${formatMoney(p.precio_unitario)}</td>
        <td><strong>${formatMoney(p.total)}</strong></td>
        <td>${formatDate(p.created_at)}</td>
        <td>
          <div class="actions">
            <button class="btn btn-sm btn-edit" onclick="startEditPedido('${p.id}')">Editar</button>
            <button class="btn btn-sm btn-danger" onclick="deletePedido('${p.id}')">Eliminar</button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    loading.style.display = "none";
    showError("pedidos-error", err.message || "No se pudo conectar con el servicio de Pedidos");
  }
}

function startEditPedido(id) {
  fetch(`${PEDIDOS_URL}/pedidos/${id}`)
    .then(res => {
      if (!res.ok) throw new Error("Pedido no encontrado");
      return res.json();
    })
    .then(p => {
      editingPedidoId = p.id;
      document.getElementById("pedido-id").value = p.id;
      document.getElementById("pedido-cantidad").value = p.cantidad;

      // Cargamos todos los productos (incluyendo inactivos) para poder mostrar el actual
      loadProductosForSelect().then(() => {
        // Si el producto ya no está activo, lo agregamos manualmente al select
        const select = document.getElementById("pedido-producto");
        let found = false;
        for (const opt of select.options) {
          if (opt.value === p.producto_id) {
            found = true;
            break;
          }
        }
        if (!found) {
          const opt = document.createElement("option");
          opt.value = p.producto_id;
          opt.textContent = `${p.producto_nombre} (histórico)`;
          select.appendChild(opt);
        }
        select.value = p.producto_id;
      });

      document.getElementById("form-pedido-title").textContent = "Editar Pedido";
      document.getElementById("btn-guardar-pedido").textContent = "Actualizar Pedido";
      document.getElementById("btn-cancelar-pedido").style.display = "inline-flex";

      document.getElementById("form-pedido").scrollIntoView({ behavior: "smooth" });
    })
    .catch(err => showToast(err.message, "error"));
}

function cancelEditPedido() {
  editingPedidoId = null;
  document.getElementById("form-pedido").reset();
  document.getElementById("pedido-id").value = "";
  document.getElementById("form-pedido-title").textContent = "Nuevo Pedido";
  document.getElementById("btn-guardar-pedido").textContent = "Crear Pedido";
  document.getElementById("btn-cancelar-pedido").style.display = "none";
  document.getElementById("pedido-cantidad").value = 1;
}

document.getElementById("btn-cancelar-pedido").addEventListener("click", cancelEditPedido);

document.getElementById("form-pedido").addEventListener("submit", async (e) => {
  e.preventDefault();

  const productoId = document.getElementById("pedido-producto").value;
  const cantidad = parseInt(document.getElementById("pedido-cantidad").value, 10);

  if (!productoId) {
    showToast("Seleccione un producto", "error");
    return;
  }

  const btn = document.getElementById("btn-guardar-pedido");
  btn.disabled = true;

  try {
    let res;
    if (editingPedidoId) {
      // Al editar se puede cambiar producto y/o cantidad
      const payload = {
        producto_id: productoId,
        cantidad: cantidad
      };
      res = await fetch(`${PEDIDOS_URL}/pedidos/${editingPedidoId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    } else {
      // Crear: solo producto_id + cantidad
      const payload = {
        producto_id: productoId,
        cantidad: cantidad
      };
      res = await fetch(`${PEDIDOS_URL}/pedidos`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    }

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      let msg = "Error al guardar pedido";

      // Manejo de errores específicos del backend
      if (errData.detail) {
        if (typeof errData.detail === "string") {
          msg = errData.detail;
        } else if (Array.isArray(errData.detail)) {
          msg = errData.detail.map(e => e.msg || e).join(", ");
        } else if (errData.detail.code) {
          // Códigos personalizados: product_not_found, product_inactive, etc.
          const code = errData.detail.code;
          if (code === "product_not_found") msg = "El producto no existe";
          else if (code === "product_inactive") msg = "El producto está inactivo y no se pueden crear pedidos";
          else if (code === "products_unavailable") msg = "El servicio de Productos no está disponible";
          else msg = errData.detail.message || code;
        }
      }
      throw new Error(msg);
    }

    showToast(editingPedidoId ? "Pedido actualizado" : "Pedido creado", "success");
    cancelEditPedido();
    loadPedidos();
  } catch (err) {
    showToast(err.message || "Error al guardar pedido", "error");
  } finally {
    btn.disabled = false;
  }
});

async function deletePedido(id) {
  if (!confirm("¿Eliminar este pedido?\n\nEsta acción es permanente.")) return;

  try {
    const res = await fetch(`${PEDIDOS_URL}/pedidos/${id}`, {
      method: "DELETE"
    });

    if (!res.ok && res.status !== 204) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(detailMessage(errData, res.status));
    }

    showToast("Pedido eliminado", "success");
    loadPedidos();
  } catch (err) {
    showToast(err.message || "No se pudo eliminar el pedido", "error");
  }
}

document.getElementById("btn-refresh-pedidos").addEventListener("click", () => {
  loadProductosForSelect();
  loadPedidos();
});

// ============================================================
// Helpers
// ============================================================
function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// ============================================================
// Inicialización
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  loadProductos();
  // Precargamos productos para el select (por si el usuario cambia de tab rápido)
  loadProductosForSelect();
});
