const integerFormatter = new Intl.NumberFormat("es-MX");

export function renderPagination(
  container,
  { page, total, pageSize, onChange, itemLabel = "resultados" }
) {
  if (!container) return;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (!total) {
    container.innerHTML = "";
    return;
  }
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  container.innerHTML = `
    <span class="pagination__info">Mostrando ${integerFormatter.format(
      start
    )}–${integerFormatter.format(end)} de ${integerFormatter.format(total)} ${itemLabel}</span>
    <div class="pagination__controls">
      <button class="icon-button" type="button" data-page="${page - 1}" ${
        page <= 1 ? "disabled" : ""
      } aria-label="Página anterior"><i class="fa-solid fa-chevron-left"></i></button>
      <span class="pagination__page">Página ${page} de ${totalPages}</span>
      <button class="icon-button" type="button" data-page="${page + 1}" ${
        page >= totalPages ? "disabled" : ""
      } aria-label="Página siguiente"><i class="fa-solid fa-chevron-right"></i></button>
    </div>
  `;
  container.querySelectorAll("[data-page]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.disabled) return;
      onChange(Number(button.dataset.page));
    });
  });
}
