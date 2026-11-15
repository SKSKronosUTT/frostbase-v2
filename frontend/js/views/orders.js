import { del, get, getUser, post, put } from "../api.js";
import {
  $,
  confirmDialog,
  dateOnly,
  dateTime,
  emptyState,
  error,
  escapeHtml,
  formValues,
  icon,
  loadingState,
  openModal,
  stateBadge,
  success,
} from "../ui.js";

export async function render(view) {
  view.innerHTML = loadingState("Cargando pedidos");
  let orders = [];
  let stores = [];
  const filters = { state: "", search: "" };

  async function load() {
    view.innerHTML = loadingState("Cargando pedidos");
    try {
      [orders, stores] = await Promise.all([get("/orders?limit=500"), get("/stores")]);
      paint();
    } catch (err) {
      view.innerHTML = `<div class="card">${emptyState("Pedidos no disponibles", err.message, "orders", '<button class="btn" data-retry>Reintentar</button>')}</div>`;
      view.querySelector("[data-retry]")?.addEventListener("click", load);
    }
  }

  function filtered() {
    const term = filters.search.trim().toLowerCase();
    return orders.filter((order) => {
      if (filters.state && order.state?.id !== filters.state) return false;
      if (!term) return true;
      return [order.store?.name, order.store?.location?.address, order.createdBy?.name?.fullName]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(term));
    });
  }

  function paint() {
    const visible = filtered();
    view.innerHTML = `
      <div class="page-head">
        <div><h2>Pedidos de entrega</h2><p>Planifica, sigue y cierra los pedidos de reabastecimiento de tiendas.</p></div>
        <div class="toolbar">
          <button class="btn" data-refresh>${icon("refresh")} Actualizar</button>
          <button class="btn btn-primary" data-new>${icon("plus")} Nuevo pedido</button>
        </div>
      </div>
      <article class="card">
        <div class="card-head">
          <div class="toolbar">
            <label class="field"><span>Estado</span><select data-filter-state>
              <option value="">Todos los estados</option>
              ${[["PO", "Pendiente"], ["LO", "Atrasado"], ["DO", "Entregado"], ["CO", "Cancelado"]]
                .map(([code, label]) => `<option value="${code}" ${filters.state === code ? "selected" : ""}>${label}</option>`)
                .join("")}
            </select></label>
            <label class="field search"><span>Buscar</span><input data-search type="search" placeholder="Tienda, dirección o creador" value="${escapeHtml(filters.search)}"></label>
          </div>
          <span class="chip">${visible.length} de ${orders.length} pedidos</span>
        </div>
        ${
          visible.length
            ? `<div class="table-wrap"><table>
                <thead><tr><th>Pedido</th><th>Tienda</th><th>Creado por</th><th>Creado</th><th>Fecha de entrega</th><th>Estado</th><th class="num">Acciones</th></tr></thead>
                <tbody>${visible
                  .map(
                    (order) => `<tr>
                      <td><span class="mono faint">#${escapeHtml(order.id.slice(0, 8))}</span></td>
                      <td><div class="cell-title">${escapeHtml(order.store?.name || "—")}</div><div class="cell-sub">${escapeHtml(order.store?.location?.address || "")}</div></td>
                      <td>${escapeHtml(order.createdBy?.name?.fullName || "—")}</td>
                      <td>${dateTime(order.date)}</td>
                      <td>${dateOnly(order.deliverDate)}</td>
                      <td>${stateBadge("order", order.state?.id, order.state?.description)}</td>
                      <td>
                        <div class="row-actions">
                          ${["PO", "LO"].includes(order.state?.id) ? `<button class="btn btn-sm" data-deliver="${order.id}">Entregar</button><button class="btn btn-sm btn-danger" data-cancel="${order.id}">Cancelar</button>` : `<span class="faint small">—</span>`}
                        </div>
                      </td>
                    </tr>`,
                  )
                  .join("")}</tbody>
              </table></div>`
            : emptyState("Ningún pedido coincide", "Ajusta los filtros o crea un nuevo pedido.", "orders")
        }
      </article>
    `;

    $("[data-refresh]").addEventListener("click", load);
    $("[data-new]").addEventListener("click", () => orderModal());
    $("[data-filter-state]").addEventListener("change", (event) => {
      filters.state = event.target.value;
      paint();
    });
    const search = $("[data-search]");
    search.addEventListener("input", (event) => {
      filters.search = event.target.value;
      const position = event.target.selectionStart;
      paint();
      const next = $("[data-search]");
      next.focus();
      next.setSelectionRange(position, position);
    });

    view.querySelectorAll("[data-deliver]").forEach((button) =>
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await put(`/orders/${button.dataset.deliver}`, { idStateOrder: "DO" });
          success("Pedido entregado", "El pedido ahora está marcado como entregado.");
          await load();
        } catch (err) {
          error("No se pudo actualizar el pedido", err.message);
          button.disabled = false;
        }
      }),
    );

    view.querySelectorAll("[data-cancel]").forEach((button) =>
      button.addEventListener("click", async () => {
        const order = orders.find((item) => item.id === button.dataset.cancel);
        const confirmed = await confirmDialog({
          title: "¿Cancelar este pedido?",
          message: `El pedido de ${order?.store?.name || "esta tienda"} se marcará como cancelado. Esta acción queda registrada en el historial.`,
          confirmLabel: "Cancelar pedido",
          danger: true,
        });
        if (!confirmed) return;
        try {
          await del(`/orders/${button.dataset.cancel}`);
          success("Pedido cancelado", "El pedido se retiró de la cola activa.");
          await load();
        } catch (err) {
          error("No se pudo cancelar el pedido", err.message);
        }
      }),
    );
  }

  function orderModal() {
    const user = getUser();
    const now = new Date();
    const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    openModal({
      title: "Nuevo pedido de entrega",
      subtitle: "La fecha de entrega se asigna automáticamente según la ruta de la tienda.",
      body: `<form id="order-form" class="form-grid">
        <label class="field full"><span>Tienda</span><select name="storeId" required>${stores
          .map((store) => `<option value="${store.id}">${escapeHtml(store.name)} — ${escapeHtml(store.location?.address || "")}</option>`)
          .join("")}</select></label>
        <label class="field full"><span>Fecha y hora del pedido</span><input type="datetime-local" name="date" value="${local}" required></label>
        <div class="note full">El planificador de rutas elige la siguiente ventana de entrega disponible según el calendario de la tienda.</div>
      </form>`,
      footer: `<button class="btn" data-cancel>Cancelar</button><button class="btn btn-primary" data-submit>Crear pedido</button>`,
      onMount(modal, close) {
        modal.querySelector("[data-cancel]").addEventListener("click", close);
        modal.querySelector("[data-submit]").addEventListener("click", async (event) => {
          const form = modal.querySelector("#order-form");
          if (!form.reportValidity()) return;
          const values = formValues(form);
          const button = event.currentTarget;
          button.disabled = true;
          try {
            await post("/orders", {
              idStore: values.storeId,
              idCreatedByUser: user?.id,
              date: new Date(values.date).toISOString(),
            });
            close();
            success("Pedido creado", "La entrega quedó programada y agregada a la cola.");
            await load();
          } catch (err) {
            error("No se pudo crear el pedido", err.message);
            button.disabled = false;
          }
        });
      },
    });
  }

  await load();
}
