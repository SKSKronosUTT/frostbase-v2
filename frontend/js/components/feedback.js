import { escapeHtml } from "../core/helpers.js";

export function tableSkeleton(_colspan, rows = 4, columns = 4) {
  return buildRows(rows, columns);
}

function buildRows(rows, columns) {
  const row = `<tr class="skeleton-row" aria-hidden="true">${Array.from(
    { length: columns },
    () => '<td><span class="skeleton skeleton--text"></span></td>'
  ).join("")}</tr>`;
  return row.repeat(rows);
}

export function tableMessage(
  colspan,
  { icon = "fa-circle-info", title, description, retryLabel = "Reintentar" } = {}
) {
  return `<tr><td colspan="${colspan}">
    <div class="empty-state">
      <div class="empty-state__icon"><i class="fa-solid ${icon}"></i></div>
      <strong>${escapeHtml(title || "")}</strong>
      ${description ? `<p>${escapeHtml(description)}</p>` : ""}
      ${
        retryLabel
          ? `<button class="btn btn--ghost btn--sm" type="button" data-retry>${escapeHtml(
              retryLabel
            )}</button>`
          : ""
      }
    </div>
  </td></tr>`;
}

export function tableError(colspan, message, { onRetry } = {}) {
  return tableMessage(colspan, {
    icon: "fa-triangle-exclamation",
    title: "No se pudo cargar la información",
    description: message,
    retryLabel: onRetry ? "Reintentar" : "",
  });
}

export function emptyRow(colspan, icon, title, description) {
  return tableMessage(colspan, { icon, title, description, retryLabel: "" });
}

export function panelState(
  { icon = "fa-circle-info", title, description } = {},
  { retryLabel = "Reintentar" } = {}
) {
  return `
    <div class="empty-state empty-state--panel">
      <div class="empty-state__icon"><i class="fa-solid ${icon}"></i></div>
      <strong>${escapeHtml(title || "")}</strong>
      ${description ? `<p>${escapeHtml(description)}</p>` : ""}
      ${
        retryLabel
          ? `<button class="btn btn--ghost btn--sm" type="button" data-retry>${escapeHtml(
              retryLabel
            )}</button>`
          : ""
      }
    </div>
  `;
}

export function renderTableState(container, html, { onRetry } = {}) {
  if (!container) return;
  container.innerHTML = html;
  const retry = container.querySelector("[data-retry]");
  if (retry && onRetry) retry.addEventListener("click", onRetry);
}

export function listSkeleton(container, rows = 4, lines = 2) {
  if (!container) return;
  container.innerHTML = Array.from(
    { length: rows },
    () =>
      `<div class="skeleton-card" aria-hidden="true">${Array.from(
        { length: lines },
        () => '<span class="skeleton skeleton--text"></span>'
      ).join("")}</div>`
  ).join("");
}

export function setAriaBusy(element, busy) {
  if (!element) return;
  element.setAttribute("aria-busy", String(Boolean(busy)));
}
