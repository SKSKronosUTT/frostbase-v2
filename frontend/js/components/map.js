export const DEFAULT_CENTER = [32.5149, -117.0382];
export const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors';

export function createMap(elementId, { center = DEFAULT_CENTER, zoom = 12 } = {}) {
  const element = document.getElementById(elementId);
  if (!element || typeof L === "undefined") {
    throw new Error("Leaflet no está disponible para inicializar el mapa");
  }
  const map = L.map(element, {
    center,
    zoom,
    zoomControl: true,
    scrollWheelZoom: true,
    attributionControl: true,
  });
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: OSM_ATTRIBUTION,
  }).addTo(map);
  setTimeout(() => map.invalidateSize(), 150);
  return map;
}

export function truckIcon({ inRoute = false, selected = false } = {}) {
  const classes = [
    "truck-marker",
    inRoute ? "truck-marker--route" : "truck-marker--idle",
    selected ? "truck-marker--selected" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return L.divIcon({
    className: "truck-marker-wrapper",
    html: `<span class="${classes}"><i class="fa-solid fa-truck"></i></span>`,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
    popupAnchor: [0, -20],
  });
}

export function numberedIcon(number, selected = false) {
  return L.divIcon({
    className: "point-marker-wrapper",
    html: `<span class="point-marker ${selected ? "point-marker--selected" : ""}">${number}</span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14],
  });
}

export function routeStyle(selected = false, hasGeometry = true) {
  return {
    color: selected ? "#2F7BFF" : "#8A9BD6",
    weight: selected ? 6 : 4,
    opacity: selected ? 0.95 : 0.65,
    lineCap: "round",
    lineJoin: "round",
    dashArray: hasGeometry ? null : "8 10",
  };
}

export function toLatLngs(geometry) {
  if (!Array.isArray(geometry)) return [];
  return geometry
    .filter(
      (coordinate) =>
        Array.isArray(coordinate) &&
        coordinate.length >= 2 &&
        Number.isFinite(Number(coordinate[0])) &&
        Number.isFinite(Number(coordinate[1]))
    )
    .map(([lat, lng]) => [Number(lat), Number(lng)]);
}

export function fitToLatLngs(map, latLngs, options = {}) {
  if (!map || !latLngs || !latLngs.length) return;
  if (latLngs.length === 1) {
    map.setView(latLngs[0], options.maxZoom || 14);
    return;
  }
  const bounds = L.latLngBounds(latLngs);
  if (!bounds.isValid()) return;
  map.fitBounds(bounds, {
    padding: [40, 40],
    maxZoom: options.maxZoom || 15,
  });
}
