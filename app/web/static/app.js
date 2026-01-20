let map = null;
let currentLayer = null;
let infoWindow = null;
const statusEl = document.getElementById('status');
const fileSelect = document.getElementById('fileSelect');
const fileInput = document.getElementById('fileInput');
const reloadBtn = document.getElementById('reloadBtn');
const refreshListBtn = document.getElementById('refreshListBtn');

function setStatus(text) {
  statusEl.textContent = text;
}

function clearLayer() {
  if (currentLayer && currentLayer.length) {
    map.remove(currentLayer);
  }
  currentLayer = null;
}

function bindOverlayPopup(overlay) {
  overlay.on('click', (e) => {
    const props = overlay.getExtData() || {};
    const name = props.school_name || props.name || '未命名';
    infoWindow.setContent(`<div>${name}</div>`);
    infoWindow.open(map, e.lnglat);
  });
}

function createOverlaysFromFeature(feature) {
  const geometry = feature?.geometry;
  if (!geometry) return [];

  const props = feature.properties || {};
  const type = geometry.type;
  const coords = geometry.coordinates;
  const overlays = [];

  if (type === 'Point') {
    overlays.push(new AMap.Marker({
      position: coords,
      extData: props
    }));
  } else if (type === 'MultiPoint') {
    coords.forEach((point) => {
      overlays.push(new AMap.Marker({
        position: point,
        extData: props
      }));
    });
  } else if (type === 'LineString') {
    overlays.push(new AMap.Polyline({
      path: coords,
      strokeColor: '#007AFF',
      strokeWeight: 2,
      extData: props
    }));
  } else if (type === 'MultiLineString') {
    coords.forEach((line) => {
      overlays.push(new AMap.Polyline({
        path: line,
        strokeColor: '#007AFF',
        strokeWeight: 2,
        extData: props
      }));
    });
  } else if (type === 'Polygon') {
    overlays.push(new AMap.Polygon({
      path: coords,
      strokeColor: '#007AFF',
      strokeWeight: 2,
      fillColor: '#007AFF',
      fillOpacity: 0.2,
      extData: props
    }));
  } else if (type === 'MultiPolygon') {
    coords.forEach((poly) => {
      overlays.push(new AMap.Polygon({
        path: poly,
        strokeColor: '#007AFF',
        strokeWeight: 2,
        fillColor: '#007AFF',
        fillOpacity: 0.2,
        extData: props
      }));
    });
  }

  return overlays;
}

function createOverlaysFromGeoJSON(geojson) {
  if (!geojson) return [];
  if (geojson.type === 'FeatureCollection') {
    return geojson.features.flatMap((f) => createOverlaysFromFeature(f));
  }
  if (geojson.type === 'Feature') {
    return createOverlaysFromFeature(geojson);
  }
  // Geometry object
  return createOverlaysFromFeature({ type: 'Feature', geometry: geojson, properties: {} });
}

function renderGeoJSON(geojson, label) {
  clearLayer();

  const overlays = createOverlaysFromGeoJSON(geojson);
  overlays.forEach((overlay) => bindOverlayPopup(overlay));
  if (overlays.length) {
    map.add(overlays);
    map.setFitView(overlays);
  }
  currentLayer = overlays;

  const count = geojson?.features?.length ?? 0;
  setStatus(`已加载: ${label} (features: ${count})`);
}

async function loadIndex() {
  try {
    const ts = Date.now();
    const resp = await fetch(`/api/polygons?_=${ts}`, {
      cache: 'no-store'
    });
    if (!resp.ok) throw new Error('文件列表读取失败');
    const files = await resp.json();

    fileSelect.innerHTML = '<option value="">-- 请选择 --</option>';
    files.forEach((f) => {
      const opt = document.createElement('option');
      opt.value = f;
      opt.textContent = f;
      fileSelect.appendChild(opt);
    });
    setStatus(`文件列表已刷新 (共 ${files.length} 个)`);
  } catch (err) {
    setStatus('未能加载文件列表，请检查服务是否正常');
  }
}

async function loadSelectedFile() {
  const file = fileSelect.value;
  if (!file) return;
  setStatus('加载中...');
  try {
    const resp = await fetch(`/api/polygons/${encodeURIComponent(file)}`);
    if (!resp.ok) throw new Error('文件读取失败');
    const geojson = await resp.json();
    renderGeoJSON(geojson, file);
  } catch (err) {
    setStatus(`加载失败: ${err.message}`);
  }
}

function initMap() {
  if (!window.AMap) {
    setStatus('AMap 加载失败，请检查 Key 或网络');
    return;
  }

  map = new AMap.Map('map', {
    zoom: 11,
    center: [120.5853, 31.2989] // 苏州中心附近 (lng, lat)
  });
  infoWindow = new AMap.InfoWindow({ offset: new AMap.Pixel(0, -20) });

  fileSelect.addEventListener('change', loadSelectedFile);
  reloadBtn.addEventListener('click', loadSelectedFile);
  refreshListBtn.addEventListener('click', loadIndex);

  fileInput.addEventListener('change', (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      try {
        const geojson = JSON.parse(reader.result);
        renderGeoJSON(geojson, file.name);
      } catch (err) {
        setStatus('本地文件解析失败');
      }
    };
    reader.readAsText(file, 'utf-8');
  });

  // 初始化加载文件列表
  loadIndex();
}

document.addEventListener('DOMContentLoaded', initMap);
