let map = null;
let infoWindow = null;
const statusEl = document.getElementById('status');
const fileSelect = document.getElementById('fileSelect');
const fileInput = document.getElementById('fileInput');
const reloadBtn = document.getElementById('reloadBtn');
const refreshListBtn = document.getElementById('refreshListBtn');
const schoolSelect = document.getElementById('schoolSelect');
const historySelect = document.getElementById('historySelect');
const restoreHistoryBtn = document.getElementById('restoreHistoryBtn');
const showPointsCheckbox = document.getElementById('showPoints');
const showItemsCheckbox = document.getElementById('showItems');
const editPolygonBtn = document.getElementById('editPolygonBtn');
const savePolygonBtn = document.getElementById('savePolygonBtn');
const editPointsBtn = document.getElementById('editPointsBtn');
const savePointsBtn = document.getElementById('savePointsBtn');
const saveDbBtn = document.getElementById('saveDbBtn');
const resetEditsBtn = document.getElementById('resetEditsBtn');
let currentPolygonLayer = null;
let currentPointsLayer = null;
let currentItemsLayer = null;
let polygonEditors = [];
let isPolygonEditing = false;
let isPointsEditing = false;
let originalPolygonGeoJSON = null;
let originalPointsGeoJSON = null;
let originalItemsGeoJSON = null;
let currentFileName = null;
let currentFileSource = 'server';
const CACHE_TTL_MS = 5 * 60 * 1000;
const responseCache = {
  polygons: new Map(),
  points: new Map(),
  items: new Map(),
  historyList: new Map(),
  historyItem: new Map(),
  index: new Map()
};

function setStatus(text) {
  statusEl.textContent = text;
}

function cloneGeoJSON(obj) {
  return obj ? JSON.parse(JSON.stringify(obj)) : null;
}

function cacheGet(map, key) {
  if (!map) return null;
  const entry = map.get(key);
  if (!entry) return null;
  if (Date.now() - entry.ts > CACHE_TTL_MS) {
    map.delete(key);
    return null;
  }
  return entry.data;
}

function cacheSet(map, key, data) {
  if (!map) return;
  map.set(key, { ts: Date.now(), data });
}

async function fetchJsonWithCache(url, cacheMap, cacheKey, force = false) {
  if (!force) {
    const cached = cacheGet(cacheMap, cacheKey);
    if (cached) return cached;
  }
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`请求失败:${resp.status}`);
  const data = await resp.json();
  cacheSet(cacheMap, cacheKey, data);
  return data;
}

function filterGeoJSONBySchool(geojson, schoolName) {
  if (!geojson || !schoolName) return geojson;
  if (geojson.type !== 'FeatureCollection') return geojson;
  const features = (geojson.features || []).filter((f) => {
    const props = f?.properties || {};
    return props.school_name === schoolName;
  });
  return { type: 'FeatureCollection', features };
}

function setSchoolOptions(geojson) {
  if (!schoolSelect) return;
  schoolSelect.innerHTML = '<option value="">全部</option>';
  if (!geojson || geojson.type !== 'FeatureCollection') return;
  const names = new Set();
  (geojson.features || []).forEach((f) => {
    const name = f?.properties?.school_name;
    if (name) names.add(name);
  });
  Array.from(names).sort().forEach((name) => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    schoolSelect.appendChild(opt);
  });
}

function setHistoryOptions(items) {
  if (!historySelect) return;
  historySelect.innerHTML = '<option value="">当前</option>';
  if (!items || !items.length) return;
  items.forEach((item) => {
    const opt = document.createElement('option');
    opt.value = item.save_id;
    const time = item.saved_at ? new Date(item.saved_at).toLocaleString('zh-CN') : '未知时间';
    opt.textContent = time;
    historySelect.appendChild(opt);
  });
}

function getSelectedSchool() {
  return schoolSelect ? schoolSelect.value : '';
}

function isSchoolFilterActive() {
  return Boolean(getSelectedSchool());
}

async function loadHistoryList(force = false) {
  if (!historySelect) return;
  if (!currentFileName || currentFileSource !== 'server') {
    setHistoryOptions([]);
    return;
  }
  try {
    const params = new URLSearchParams({
      file_name: currentFileName
    });
    const school = getSelectedSchool();
    if (school) params.set('school_name', school);
    const cacheKey = params.toString();
    const items = await fetchJsonWithCache(
      `/api/history?${params.toString()}`,
      responseCache.historyList,
      cacheKey,
      force
    );
    setHistoryOptions(items);
  } catch (err) {
    setStatus('历史列表读取失败');
    setHistoryOptions([]);
  }
}

async function loadHistoryById(saveId) {
  if (!saveId) return;
  setStatus('加载历史版本中...');
  disableAllEditing();
  clearAllLayers();
  try {
    const data = await fetchJsonWithCache(
      `/api/history/${encodeURIComponent(saveId)}`,
      responseCache.historyItem,
      saveId
    );
    applyHistoryData(data, { asCurrent: false });
  } catch (err) {
    setStatus(`历史版本加载失败: ${err.message}`);
  }
}

function applyHistoryData(data, options = {}) {
  const asCurrent = Boolean(options.asCurrent);
  currentFileName = data.file_name || currentFileName;
  currentFileSource = asCurrent ? 'server' : 'history';
  if (schoolSelect) {
    schoolSelect.value = data.school_name || '';
  }
  clearAllLayers();
  if (data.polygons) {
    renderGeoJSON(
      data.polygons,
      `${currentFileName} (${asCurrent ? '恢复' : '历史'})`,
      { skipOriginal: !asCurrent }
    );
  } else {
    clearPolygonLayer();
  }
  if (showPointsCheckbox.checked && data.points) {
    renderPointsGeoJSON(
      data.points,
      `${currentFileName} (${asCurrent ? '恢复' : '历史'})`,
      { skipOriginal: !asCurrent }
    );
  } else {
    clearPointsLayer();
  }
  clearItemsLayer();
  if (showItemsCheckbox.checked) {
    setStatus('历史版本不包含细分面');
  }
  if (asCurrent && historySelect) {
    historySelect.value = '';
  }
}

async function restoreHistoryAsCurrent() {
  if (!historySelect || !historySelect.value) {
    setStatus('请先选择一个历史版本');
    return;
  }
  setStatus('正在恢复历史版本...');
  try {
    const resp = await fetch(`/api/history/${encodeURIComponent(historySelect.value)}`);
    if (!resp.ok) throw new Error('历史版本读取失败');
    const data = await resp.json();
    applyHistoryData(data, { asCurrent: true });
    setStatus('已恢复为当前版本，可继续编辑并保存');
    await loadHistoryList();
  } catch (err) {
    setStatus(`恢复失败: ${err.message}`);
  }
}

function clearPolygonLayer() {
  if (currentPolygonLayer && currentPolygonLayer.length) {
    map.remove(currentPolygonLayer);
  }
  currentPolygonLayer = null;
}

function clearPointsLayer() {
  if (currentPointsLayer && currentPointsLayer.length) {
    map.remove(currentPointsLayer);
  }
  currentPointsLayer = null;
}

function clearItemsLayer() {
  if (currentItemsLayer && currentItemsLayer.length) {
    map.remove(currentItemsLayer);
  }
  currentItemsLayer = null;
}

function clearAllLayers() {
  clearPolygonLayer();
  clearPointsLayer();
  clearItemsLayer();
}

function closePolygonEditors() {
  polygonEditors.forEach((editor) => editor.close());
  polygonEditors = [];
  isPolygonEditing = false;
  editPolygonBtn.textContent = '编辑面';
}

function setMarkersDraggable(overlays, draggable) {
  if (!overlays) return;
  overlays.forEach((overlay) => {
    if (overlay instanceof AMap.Marker) {
      overlay.setDraggable(draggable);
    }
  });
}

function disableAllEditing() {
  closePolygonEditors();
  if (isPointsEditing) {
    setMarkersDraggable(currentPointsLayer, false);
    isPointsEditing = false;
    editPointsBtn.textContent = '编辑点';
  }
}

function bindOverlayPopup(overlay) {
  overlay.on('click', (e) => {
    const props = overlay.getExtData() || {};
    const name = props.name || props.school_name || '未命名';
    const kind = props.kind ? ` (${props.kind})` : '';
    infoWindow.setContent(`<div>${name}${kind}</div>`);
    infoWindow.open(map, e.lnglat);

    if (isPointsEditing && overlay instanceof AMap.Marker) {
      const current = overlay.getPosition();
      const input = window.prompt(
        '输入坐标，格式：lng,lat',
        `${current.lng},${current.lat}`
      );
      if (!input) return;
      const parts = input.split(',').map((p) => p.trim());
      if (parts.length !== 2) {
        setStatus('坐标格式错误，应为 lng,lat');
        return;
      }
      const lng = Number(parts[0]);
      const lat = Number(parts[1]);
      if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
        setStatus('坐标必须为数字');
        return;
      }
      overlay.setPosition([lng, lat]);
      setStatus('坐标已更新，记得保存点集');
    }
  });
}

function getPointClass(props) {
  if (props.kind === 'boundary') return 'point-marker point-boundary';
  if (props.kind === 'include') return 'point-marker point-include';
  return 'point-marker';
}

function createOverlaysFromFeature(feature, options = {}) {
  const geometry = feature?.geometry;
  if (!geometry) return [];

  const props = feature.properties || {};
  const type = geometry.type;
  const coords = geometry.coordinates;
  const overlays = [];

  if (type === 'Point') {
    if (options.pointStyle === 'dot') {
      overlays.push(new AMap.Marker({
        position: coords,
        content: `<div class="${getPointClass(props)}"></div>`,
        offset: new AMap.Pixel(-4, -4),
        extData: props
      }));
    } else {
      overlays.push(new AMap.Marker({
        position: coords,
        extData: props
      }));
    }
  } else if (type === 'MultiPoint') {
    coords.forEach((point) => {
      if (options.pointStyle === 'dot') {
        overlays.push(new AMap.Marker({
          position: point,
          content: `<div class="${getPointClass(props)}"></div>`,
          offset: new AMap.Pixel(-4, -4),
          extData: props
        }));
      } else {
        overlays.push(new AMap.Marker({
          position: point,
          extData: props
        }));
      }
    });
  } else if (type === 'LineString') {
    overlays.push(new AMap.Polyline({
      path: coords,
      strokeColor: options.strokeColor || '#007AFF',
      strokeWeight: 2,
      extData: props
    }));
  } else if (type === 'MultiLineString') {
    coords.forEach((line) => {
      overlays.push(new AMap.Polyline({
        path: line,
        strokeColor: options.strokeColor || '#007AFF',
        strokeWeight: 2,
        extData: props
      }));
    });
  } else if (type === 'Polygon') {
    overlays.push(new AMap.Polygon({
      path: coords,
      strokeColor: options.strokeColor || '#007AFF',
      strokeWeight: 2,
      fillColor: options.fillColor || '#007AFF',
      fillOpacity: options.fillOpacity ?? 0.2,
      extData: props
    }));
  } else if (type === 'MultiPolygon') {
    coords.forEach((poly) => {
      overlays.push(new AMap.Polygon({
        path: poly,
        strokeColor: options.strokeColor || '#007AFF',
        strokeWeight: 2,
        fillColor: options.fillColor || '#007AFF',
        fillOpacity: options.fillOpacity ?? 0.2,
        extData: props
      }));
    });
  }

  return overlays;
}

function createOverlaysFromGeoJSON(geojson, options = {}) {
  if (!geojson) return [];
  if (geojson.type === 'FeatureCollection') {
    return geojson.features.flatMap((f) => createOverlaysFromFeature(f, options));
  }
  if (geojson.type === 'Feature') {
    return createOverlaysFromFeature(geojson, options);
  }
  // Geometry object
  return createOverlaysFromFeature(
    { type: 'Feature', geometry: geojson, properties: {} },
    options
  );
}

function renderGeoJSON(geojson, label, options = {}) {
  clearPolygonLayer();

  const overlays = createOverlaysFromGeoJSON(geojson);
  overlays.forEach((overlay) => bindOverlayPopup(overlay));
  if (overlays.length) {
    map.add(overlays);
    map.setFitView(overlays);
  }
  currentPolygonLayer = overlays;
  if (!options.skipOriginal) {
    originalPolygonGeoJSON = cloneGeoJSON(geojson);
  }

  const count = geojson?.features?.length ?? 0;
  const schoolTag = getSelectedSchool() ? ` | 校区: ${getSelectedSchool()}` : '';
  setStatus(`已加载: ${label} (features: ${count})${schoolTag}`);
}

function renderPointsGeoJSON(geojson, label, options = {}) {
  clearPointsLayer();
  const overlays = createOverlaysFromGeoJSON(geojson, { pointStyle: 'dot' });
  overlays.forEach((overlay) => bindOverlayPopup(overlay));
  if (overlays.length) {
    map.add(overlays);
  }
  currentPointsLayer = overlays;
  if (!options.skipOriginal) {
    originalPointsGeoJSON = cloneGeoJSON(geojson);
  }
  const count = geojson?.features?.length ?? 0;
  const schoolTag = getSelectedSchool() ? ` | 校区: ${getSelectedSchool()}` : '';
  setStatus(`已加载点集: ${label} (points: ${count})${schoolTag}`);
}

function renderItemsGeoJSON(geojson, label, options = {}) {
  clearItemsLayer();
  const overlays = createOverlaysFromGeoJSON(geojson, {
    strokeColor: '#00C853',
    fillColor: '#00C853',
    fillOpacity: 0.18
  });
  overlays.forEach((overlay) => bindOverlayPopup(overlay));
  if (overlays.length) {
    map.add(overlays);
  }
  currentItemsLayer = overlays;
  if (!options.skipOriginal) {
    originalItemsGeoJSON = cloneGeoJSON(geojson);
  }
  const count = geojson?.features?.length ?? 0;
  const schoolTag = getSelectedSchool() ? ` | 校区: ${getSelectedSchool()}` : '';
  setStatus(`已加载细分面: ${label} (features: ${count})${schoolTag}`);
}

function toLngLatArray(path) {
  return path.map((p) => [p.lng, p.lat]);
}

function polygonPathToCoordinates(path) {
  if (!path || !path.length) return [];
  if (Array.isArray(path[0])) {
    return path.map((ring) => toLngLatArray(ring));
  }
  return [toLngLatArray(path)];
}

function overlaysToGeoJSON(overlays, geometryType) {
  const features = [];
  if (!overlays) return { type: 'FeatureCollection', features };
  overlays.forEach((overlay) => {
    const props = overlay.getExtData?.() || {};
    if (geometryType === 'Point' && overlay instanceof AMap.Marker) {
      const pos = overlay.getPosition();
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [pos.lng, pos.lat] },
        properties: props
      });
    } else if (geometryType === 'Polygon' && overlay instanceof AMap.Polygon) {
      const path = overlay.getPath();
      const coordinates = polygonPathToCoordinates(path);
      features.push({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates },
        properties: props
      });
    } else if (geometryType === 'LineString' && overlay instanceof AMap.Polyline) {
      const path = overlay.getPath();
      features.push({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: toLngLatArray(path) },
        properties: props
      });
    }
  });
  return { type: 'FeatureCollection', features };
}

async function saveGeoJSON(kind, geojson) {
  if (!currentFileName || currentFileSource !== 'server') {
    setStatus('本地文件仅预览，无法保存到服务器');
    return;
  }
  const endpoint = kind === 'points'
    ? `/api/points/${encodeURIComponent(currentFileName)}`
    : kind === 'items'
      ? `/api/items/${encodeURIComponent(currentFileName)}`
      : `/api/polygons/${encodeURIComponent(currentFileName)}`;
  setStatus('保存中...');
  const resp = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(geojson)
  });
  if (!resp.ok) {
    throw new Error('保存失败');
  }
  if (kind === 'points') {
    cacheSet(responseCache.points, currentFileName, geojson);
  } else if (kind === 'items') {
    cacheSet(responseCache.items, currentFileName, geojson);
  } else {
    cacheSet(responseCache.polygons, currentFileName, geojson);
  }
  setStatus('保存成功');
}

async function saveCurrentToDatabase() {
  setStatus('正在保存全部数据到数据库...');
  const resp = await fetch('/api/save_all', { method: 'POST' });
  if (!resp.ok) {
    const detail = await resp.text();
    setStatus(`保存失败: ${detail}`);
    return;
  }
  const result = await resp.json();
  const errCount = result?.errors?.length || 0;
  if (errCount) {
    setStatus(`已保存到数据库，但有 ${errCount} 个文件失败`);
  } else {
    setStatus('已保存到数据库');
  }
  if (currentFileName && currentFileSource !== 'history') {
    responseCache.historyList.clear();
    await loadHistoryList(true);
  }
}

function togglePolygonEditing() {
  if (!currentPolygonLayer || !currentPolygonLayer.length) {
    setStatus('未加载面数据，无法编辑');
    return;
  }
  if (isSchoolFilterActive()) {
    setStatus('请先切换到全部校区再编辑');
    return;
  }
  if (isPolygonEditing) {
    closePolygonEditors();
    return;
  }
  AMap.plugin(['AMap.PolyEditor'], () => {
    closePolygonEditors();
    currentPolygonLayer.forEach((overlay) => {
      if (overlay instanceof AMap.Polygon) {
        const editor = new AMap.PolyEditor(map, overlay);
        editor.open();
        polygonEditors.push(editor);
      }
    });
    isPolygonEditing = true;
    editPolygonBtn.textContent = '结束编辑面';
    setStatus('面编辑已开启');
  });
}

function togglePointsEditing() {
  if (!currentPointsLayer || !currentPointsLayer.length) {
    setStatus('未加载点集，无法编辑');
    return;
  }
  if (isSchoolFilterActive()) {
    setStatus('请先切换到全部校区再编辑');
    return;
  }
  isPointsEditing = !isPointsEditing;
  setMarkersDraggable(currentPointsLayer, isPointsEditing);
  editPointsBtn.textContent = isPointsEditing ? '结束编辑点' : '编辑点';
  setStatus(isPointsEditing ? '点编辑已开启' : '点编辑已关闭');
}

function resetEdits() {
  disableAllEditing();
  if (currentFileSource === 'server') {
    loadSelectedFile();
    return;
  }
  if (originalPolygonGeoJSON) {
    clearAllLayers();
    renderGeoJSON(originalPolygonGeoJSON, currentFileName || '本地文件');
  }
  if (originalPointsGeoJSON && showPointsCheckbox.checked) {
    renderPointsGeoJSON(originalPointsGeoJSON, currentFileName || '本地文件');
  }
  if (originalItemsGeoJSON && showItemsCheckbox.checked) {
    renderItemsGeoJSON(originalItemsGeoJSON, currentFileName || '本地文件');
  }
  setStatus('已撤销到原始数据');
}

function applySchoolFilter() {
  if (historySelect && historySelect.value) {
    setStatus('历史版本模式下无法筛选');
    return;
  }
  const school = getSelectedSchool();
  if (originalPolygonGeoJSON) {
    const filtered = filterGeoJSONBySchool(originalPolygonGeoJSON, school);
    renderGeoJSON(filtered, currentFileName || '文件', { skipOriginal: true });
  }
  if (showPointsCheckbox.checked) {
    if (originalPointsGeoJSON) {
      const filtered = filterGeoJSONBySchool(originalPointsGeoJSON, school);
      renderPointsGeoJSON(filtered, currentFileName || '文件', { skipOriginal: true });
    } else if (currentFileSource === 'server' && currentFileName) {
      loadPointsForFile(currentFileName);
    }
  } else {
    clearPointsLayer();
  }
  if (showItemsCheckbox.checked) {
    if (originalItemsGeoJSON) {
      const filtered = filterGeoJSONBySchool(originalItemsGeoJSON, school);
      renderItemsGeoJSON(filtered, currentFileName || '文件', { skipOriginal: true });
    } else if (currentFileSource === 'server' && currentFileName) {
      loadItemsForFile(currentFileName);
    }
  } else {
    clearItemsLayer();
  }
}

async function loadIndex(force = false) {
  try {
    const files = await fetchJsonWithCache(
      '/api/polygons',
      responseCache.index,
      'index',
      force
    );

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
  currentFileName = file;
  currentFileSource = 'server';
  disableAllEditing();
  if (schoolSelect) {
    schoolSelect.value = '';
  }
  if (historySelect) {
    historySelect.value = '';
  }
  setStatus('加载中...');
  clearAllLayers();
  try {
    const geojson = await fetchJsonWithCache(
      `/api/polygons/${encodeURIComponent(file)}`,
      responseCache.polygons,
      file
    );
    setSchoolOptions(geojson);
    renderGeoJSON(geojson, file);
    if (showPointsCheckbox.checked) {
      await loadPointsForFile(file);
    }
    if (showItemsCheckbox.checked) {
      await loadItemsForFile(file);
    }
    await loadHistoryList();
  } catch (err) {
    setStatus(`加载失败: ${err.message}`);
  }
}

async function loadPointsForFile(file) {
  try {
    let geojson = null;
    try {
      geojson = await fetchJsonWithCache(
        `/api/points/${encodeURIComponent(file)}`,
        responseCache.points,
        file
      );
    } catch (err) {
      if (err?.message && err.message.includes('404')) {
        setStatus('点集文件不存在（请先生成 points 文件）');
        return;
      }
      throw err;
    }
    originalPointsGeoJSON = cloneGeoJSON(geojson);
    const filtered = filterGeoJSONBySchool(geojson, getSelectedSchool());
    renderPointsGeoJSON(filtered, file, { skipOriginal: true });
  } catch (err) {
    setStatus(`点集加载失败: ${err.message}`);
  }
}

async function loadItemsForFile(file) {
  try {
    let geojson = null;
    try {
      geojson = await fetchJsonWithCache(
        `/api/items/${encodeURIComponent(file)}`,
        responseCache.items,
        file
      );
    } catch (err) {
      if (err?.message && err.message.includes('404')) {
        setStatus('细分面文件不存在（请先生成 items 文件）');
        return;
      }
      throw err;
    }
    originalItemsGeoJSON = cloneGeoJSON(geojson);
    const filtered = filterGeoJSONBySchool(geojson, getSelectedSchool());
    renderItemsGeoJSON(filtered, file, { skipOriginal: true });
  } catch (err) {
    setStatus(`细分面加载失败: ${err.message}`);
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
refreshListBtn.addEventListener('click', () => loadIndex(true));
  showPointsCheckbox.addEventListener('change', () => {
    if (showPointsCheckbox.checked) {
      if (fileSelect.value) {
        loadPointsForFile(fileSelect.value);
      }
    } else {
      clearPointsLayer();
    }
  });
  showItemsCheckbox.addEventListener('change', () => {
    if (showItemsCheckbox.checked) {
      if (fileSelect.value) {
        loadItemsForFile(fileSelect.value);
      }
    } else {
      clearItemsLayer();
    }
  });

  editPolygonBtn.addEventListener('click', togglePolygonEditing);
  savePolygonBtn.addEventListener('click', async () => {
    try {
      if (isSchoolFilterActive()) {
        setStatus('请先切换到全部校区再保存');
        return;
      }
      if (!currentPolygonLayer || !currentPolygonLayer.length) {
        setStatus('未加载面数据，无法保存');
        return;
      }
      const geojson = overlaysToGeoJSON(currentPolygonLayer, 'Polygon');
      await saveGeoJSON('polygons', geojson);
      originalPolygonGeoJSON = cloneGeoJSON(geojson);
    } catch (err) {
      setStatus(`保存失败: ${err.message}`);
    }
  });

  editPointsBtn.addEventListener('click', togglePointsEditing);
  savePointsBtn.addEventListener('click', async () => {
    try {
      if (isSchoolFilterActive()) {
        setStatus('请先切换到全部校区再保存');
        return;
      }
      if (!currentPointsLayer || !currentPointsLayer.length) {
        setStatus('未加载点集，无法保存');
        return;
      }
      const geojson = overlaysToGeoJSON(currentPointsLayer, 'Point');
      await saveGeoJSON('points', geojson);
      originalPointsGeoJSON = cloneGeoJSON(geojson);
    } catch (err) {
      setStatus(`保存失败: ${err.message}`);
    }
  });

  saveDbBtn.addEventListener('click', () => {
    saveCurrentToDatabase().catch((err) => {
      setStatus(`保存失败: ${err.message}`);
    });
  });

  resetEditsBtn.addEventListener('click', resetEdits);
  if (schoolSelect) {
    schoolSelect.addEventListener('change', () => {
      disableAllEditing();
      if (historySelect) {
        historySelect.value = '';
      }
      applySchoolFilter();
      loadHistoryList();
    });
  }
  if (historySelect) {
    historySelect.addEventListener('change', () => {
      disableAllEditing();
      if (!historySelect.value) {
        currentFileSource = 'server';
        loadSelectedFile();
        return;
      }
      loadHistoryById(historySelect.value);
    });
  }

fileInput.addEventListener('change', (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = () => {
    try {
      const geojson = JSON.parse(reader.result);
        currentFileName = file.name;
        currentFileSource = 'local';
        disableAllEditing();
      if (schoolSelect) {
        schoolSelect.value = '';
      }
        if (historySelect) {
          historySelect.value = '';
          setHistoryOptions([]);
        }
        clearAllLayers();
      setSchoolOptions(geojson);
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
