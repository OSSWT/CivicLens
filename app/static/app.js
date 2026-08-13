"use strict";

const state = {
  reports: [], map: null, markers: [], selectedReport: null,
  selectedLocation: { lat: 3.139, lng: 101.6869 }, nearbyOnly: false,
};
const statusLabels = { reported: "Reported", in_progress: "In progress", resolved: "Resolved" };
const markerColors = { reported: "#e5a328", in_progress: "#3678c8", resolved: "#176b4d" };

$(async function initialize() {
  bindEvents();
  await checkApi();
  const config = await $.getJSON("/api/config/public");
  state.selectedLocation = { lat: config.default_center[0], lng: config.default_center[1] };
  syncLocationInputs();
  if (config.maps_enabled) {
    try {
      await loadGoogleMaps(config.google_maps_api_key);
      await initializeMap(config.default_center);
    } catch (error) {
      console.error("Google Maps failed to load", error);
      showMapFallback();
    }
  } else showMapFallback();
  await loadReports();
});

function bindEvents() {
  $("#categoryFilter, #statusFilter").on("change", loadReports);
  $("#resetFilters").on("click", function resetFilters() {
    $("#categoryFilter, #statusFilter").val(""); state.nearbyOnly = false;
    $("#nearbyButton").removeClass("btn-secondary").addClass("btn-outline-secondary"); loadReports();
  });
  $("#nearbyButton").on("click", function toggleNearby() {
    state.nearbyOnly = !state.nearbyOnly;
    $(this).toggleClass("btn-outline-secondary", !state.nearbyOnly).toggleClass("btn-secondary", state.nearbyOnly);
    loadReports();
  });
  $("#reportForm").on("submit", submitReport);
  $("#reportList").on("click", ".report-card", function openCard() { openReport($(this).data("report-id")); });
  $("#detailBody").on("submit", "#statusForm", updateStatus);
  $("#detailBody").on("submit", "#afterPhotoForm", uploadAfterPhoto);
  $("#detailBody").on("click", "#deleteReport", deleteReport);
}

async function checkApi() {
  try {
    await $.getJSON("/api/health");
    $("#apiStatus").text("API connected").removeClass("text-danger").addClass("text-success");
  } catch (error) {
    $("#apiStatus").text("API unavailable").removeClass("text-secondary").addClass("text-danger"); throw error;
  }
}

function loadGoogleMaps(apiKey) {
  return new Promise(function createGoogleScript(resolve, reject) {
    window.civicLensMapsReady = resolve;
    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&loading=async&callback=civicLensMapsReady&v=weekly`;
    script.async = true; script.onerror = reject; document.head.appendChild(script);
  });
}

async function initializeMap(defaultCenter) {
  const [{ Map }, { AdvancedMarkerElement, PinElement }] = await Promise.all([
    google.maps.importLibrary("maps"), google.maps.importLibrary("marker"),
  ]);
  state.AdvancedMarkerElement = AdvancedMarkerElement; state.PinElement = PinElement;
  state.map = new Map(document.getElementById("map"), {
    center: { lat: defaultCenter[0], lng: defaultCenter[1] }, zoom: 13,
    mapId: "DEMO_MAP_ID", mapTypeControl: false, streetViewControl: false,
  });
  state.map.addListener("click", function chooseLocation(event) {
    state.selectedLocation = { lat: event.latLng.lat(), lng: event.latLng.lng() };
    syncLocationInputs(); showToast("Location selected. Open “Report an issue” to continue.");
  });
}

function showMapFallback() { $("#map").addClass("d-none"); $("#mapFallback").removeClass("d-none"); }

async function loadReports() {
  const params = {}; const category = $("#categoryFilter").val(); const status = $("#statusFilter").val();
  if (category) params.category = category; if (status) params.status = status;
  let endpoint = "/api/reports";
  if (state.nearbyOnly) {
    const center = state.map ? state.map.getCenter() : state.selectedLocation;
    params.latitude = typeof center.lat === "function" ? center.lat() : center.lat;
    params.longitude = typeof center.lng === "function" ? center.lng() : center.lng;
    params.radius_meters = 5000; endpoint = "/api/reports/nearby";
  }
  $("#resultSummary").text("Loading reports…");
  try { state.reports = await $.getJSON(endpoint, params); renderReports(); }
  catch (error) { $("#resultSummary").text("Could not load reports"); showToast(readApiError(error)); }
}

function renderReports() {
  const $list = $("#reportList").empty();
  $("#emptyState").toggleClass("d-none", state.reports.length !== 0);
  $("#resultSummary").text(`${state.reports.length} report${state.reports.length === 1 ? "" : "s"}`);
  state.reports.forEach(function appendReport(report) {
    const coordinates = report.location.coordinates;
    $list.append($("<button>", { class: "report-card", type: "button", "data-report-id": report.id, html: `
      <div class="d-flex align-items-center justify-content-between gap-2"><span class="category-badge">${escapeHtml(report.category)}</span><span class="status-badge status-${escapeHtml(report.status)}">${escapeHtml(statusLabels[report.status])}</span></div>
      <h3>${escapeHtml(report.title)}</h3><p>${escapeHtml(report.description || "No additional description")}</p>
      <div class="small text-secondary mt-2">${coordinates[1].toFixed(4)}, ${coordinates[0].toFixed(4)}</div>`, }));
  });
  const active = state.reports.filter((report) => report.status !== "resolved").length;
  $("#totalCount").text(state.reports.length); $("#activeCount").text(active); $("#resolvedCount").text(state.reports.length - active);
  renderMarkers();
}

function renderMarkers() {
  state.markers.forEach((marker) => { marker.map = null; }); state.markers = [];
  if (!state.map || !state.AdvancedMarkerElement) return;
  state.reports.forEach(function addMarker(report) {
    const pin = new state.PinElement({ background: markerColors[report.status], borderColor: "#ffffff", glyphColor: "#ffffff" });
    const marker = new state.AdvancedMarkerElement({ map: state.map, position: { lat: report.location.coordinates[1], lng: report.location.coordinates[0] }, title: report.title, content: pin.element });
    marker.addListener("click", () => openReport(report.id)); state.markers.push(marker);
  });
}

async function submitReport(event) {
  event.preventDefault(); const $button = $("#submitReport").prop("disabled", true).text("Analyzing photo…"); $("#reportError").addClass("d-none");
  try {
    const report = await ajaxForm("/api/reports", new FormData(event.currentTarget));
    bootstrap.Modal.getOrCreateInstance(document.getElementById("reportModal")).hide(); event.currentTarget.reset(); syncLocationInputs(); await loadReports();
    showToast(report.before_photo.analysis.accepted ? "Report submitted with clear photo evidence." : `Report submitted with ${report.before_photo.analysis.warnings.length} photo warning(s).`);
  } catch (error) { $("#reportError").text(readApiError(error)).removeClass("d-none"); }
  finally { $button.prop("disabled", false).text("Submit report"); }
}

function openReport(reportId) {
  const report = state.reports.find((item) => item.id === reportId); if (!report) return;
  state.selectedReport = report; $("#detailMeta").text(`${report.category.toUpperCase()} · ${statusLabels[report.status].toUpperCase()}`); $("#detailTitle").text(report.title); $("#detailBody").html(detailTemplate(report));
  bootstrap.Modal.getOrCreateInstance(document.getElementById("detailModal")).show();
}

function detailTemplate(report) {
  const before = report.before_photo; const after = report.after_photo;
  const warnings = before.analysis.warnings.length ? `<ul class="small text-warning-emphasis mb-0">${before.analysis.warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>` : '<p class="small text-success mb-0">Photo passed every quality check.</p>';
  const afterColumn = after ? `<div class="col-md-6"><p class="eyebrow mb-2">AFTER</p><img class="evidence-photo" src="${escapeHtml(after.url)}" alt="Resolution evidence"></div>` : '<div class="col-md-6"><div class="map-fallback h-100"><div><p class="mb-1 fw-semibold">No after photo yet</p><p class="small text-secondary mb-0">Add one when the issue is resolved.</p></div></div></div>';
  const change = report.change_analysis ? `<div class="analysis-metric"><span>Visual difference</span><strong>${report.change_analysis.mean_difference_percent}%</strong></div><div class="analysis-metric"><span>Histogram similarity</span><strong>${report.change_analysis.histogram_similarity}</strong></div>` : "";
  return `<div class="row g-4"><div class="col-lg-8"><p class="text-secondary">${escapeHtml(report.description || "No additional description")}</p><div class="row g-3"><div class="col-md-6"><p class="eyebrow mb-2">BEFORE</p><img class="evidence-photo" src="${escapeHtml(before.url)}" alt="Original issue evidence"></div>${afterColumn}</div></div>
    <div class="col-lg-4"><div class="analysis-panel mb-3"><h3 class="h6">OpenCV evidence check</h3><div class="analysis-metric"><span>Resolution</span><strong>${before.analysis.width} × ${before.analysis.height}</strong></div><div class="analysis-metric"><span>Brightness</span><strong>${before.analysis.brightness}</strong></div><div class="analysis-metric"><span>Blur score</span><strong>${before.analysis.blur_score}</strong></div>${change}<div class="mt-2">${warnings}</div></div>
    <div class="admin-panel"><h3 class="h6">Admin actions</h3><label class="form-label small" for="adminKey">Admin key</label><input id="adminKey" class="form-control form-control-sm mb-3" type="password" autocomplete="off" placeholder="X-Admin-Key"><form id="statusForm" class="d-flex gap-2 mb-3"><select class="form-select form-select-sm" name="status"><option value="reported" ${report.status === "reported" ? "selected" : ""}>Reported</option><option value="in_progress" ${report.status === "in_progress" ? "selected" : ""}>In progress</option><option value="resolved" ${report.status === "resolved" ? "selected" : ""}>Resolved</option></select><button class="btn btn-sm btn-outline-primary" type="submit">Update</button></form><form id="afterPhotoForm" class="mb-3"><label class="form-label small" for="afterPhoto">Resolution photo</label><div class="input-group input-group-sm"><input id="afterPhoto" class="form-control" name="photo" type="file" accept="image/jpeg,image/png,image/webp" required><button class="btn btn-outline-primary" type="submit">Upload</button></div></form><button id="deleteReport" class="btn btn-sm btn-link text-danger p-0" type="button">Delete report</button></div></div></div>`;
}

async function updateStatus(event) {
  event.preventDefault(); const status = $(event.currentTarget).find("[name=status]").val();
  try { const updated = await $.ajax({ url: `/api/reports/${state.selectedReport.id}/status`, method: "PATCH", contentType: "application/json", headers: adminHeaders(), data: JSON.stringify({ status }) }); await refreshDetail(updated); showToast("Report status updated."); }
  catch (error) { showToast(readApiError(error)); }
}

async function uploadAfterPhoto(event) {
  event.preventDefault();
  try { const updated = await ajaxForm(`/api/reports/${state.selectedReport.id}/after-photo`, new FormData(event.currentTarget), adminHeaders()); await refreshDetail(updated); showToast("Resolution evidence analyzed and added."); }
  catch (error) { showToast(readApiError(error)); }
}

async function deleteReport() {
  if (!window.confirm("Delete this report and both local photos?")) return;
  try { await $.ajax({ url: `/api/reports/${state.selectedReport.id}`, method: "DELETE", headers: adminHeaders() }); bootstrap.Modal.getOrCreateInstance(document.getElementById("detailModal")).hide(); await loadReports(); showToast("Report deleted."); }
  catch (error) { showToast(readApiError(error)); }
}

async function refreshDetail(updated) { await loadReports(); state.selectedReport = updated; $("#detailMeta").text(`${updated.category.toUpperCase()} · ${statusLabels[updated.status].toUpperCase()}`); $("#detailBody").html(detailTemplate(updated)); }
function ajaxForm(url, formData, headers = {}) { return $.ajax({ url, method: "POST", data: formData, headers, processData: false, contentType: false }); }
function adminHeaders() { return { "X-Admin-Key": $("#adminKey").val() || "" }; }
function syncLocationInputs() { $("#reportLatitude").val(state.selectedLocation.lat.toFixed(6)); $("#reportLongitude").val(state.selectedLocation.lng.toFixed(6)); }
function showToast(message) { $("#toastMessage").text(message); bootstrap.Toast.getOrCreateInstance(document.getElementById("appToast")).show(); }
function readApiError(error) { const detail = error?.responseJSON?.detail; if (Array.isArray(detail)) return detail.map((item) => item.msg).join(" "); return detail || "Something went wrong. Please try again."; }
function escapeHtml(value) { return $("<div>").text(value ?? "").html(); }
