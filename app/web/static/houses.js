const STORAGE_KEY = 'houseManager.items';
let houses = [];
let editingId = null;

const houseListEl = document.getElementById('houseList');
const searchInput = document.getElementById('houseSearch');
const statusFilter = document.getElementById('houseStatusFilter');
const addBtn = document.getElementById('houseAddBtn');
const formPanel = document.getElementById('houseFormPanel');
const formTitle = document.getElementById('houseFormTitle');
const houseForm = document.getElementById('houseForm');
const cancelBtn = document.getElementById('houseCancelBtn');

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    houses = raw ? JSON.parse(raw) : [];
  } catch {
    houses = [];
  }
}

function saveToStorage() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(houses));
}

function formatArea(value) {
  if (value === '' || value === null || value === undefined) return '-';
  const num = Number(value);
  return Number.isFinite(num) ? `${num.toFixed(2)} ㎡` : '-';
}

function renderList() {
  const keyword = searchInput.value.trim();
  const statusValue = statusFilter.value;
  const items = houses.filter((item) => {
    const matchStatus = !statusValue || item.status === statusValue;
    if (!keyword) return matchStatus;
    const keywordLower = keyword.toLowerCase();
    const text = `${item.name} ${item.address}`.toLowerCase();
    return matchStatus && text.includes(keywordLower);
  });

  if (!items.length) {
    houseListEl.innerHTML = '<div class="empty-state">暂无房屋信息</div>';
    return;
  }

  houseListEl.innerHTML = items.map((item) => `
    <article class="house-card">
      <div class="house-card-main">
        <h3>${item.name}</h3>
        <div class="house-meta">
          <span>${item.address}</span>
          <span>${formatArea(item.area)}</span>
          <span class="status-tag">${item.status}</span>
        </div>
        <p class="house-note">${item.note || '—'}</p>
      </div>
      <div class="house-actions">
        <button data-action="edit" data-id="${item.id}">编辑</button>
        <button data-action="delete" data-id="${item.id}" class="danger">删除</button>
      </div>
    </article>
  `).join('');
}

function resetForm() {
  editingId = null;
  houseForm.reset();
  formTitle.textContent = '新增房屋';
}

function openForm(item) {
  formPanel.classList.remove('hidden');
  if (!item) {
    resetForm();
    return;
  }
  editingId = item.id;
  formTitle.textContent = '编辑房屋';
  houseForm.name.value = item.name || '';
  houseForm.address.value = item.address || '';
  houseForm.area.value = item.area ?? '';
  houseForm.status.value = item.status || '空置';
  houseForm.note.value = item.note || '';
}

function closeForm() {
  formPanel.classList.add('hidden');
  resetForm();
}

function upsertHouse(payload) {
  if (editingId) {
    houses = houses.map((item) => (item.id === editingId ? { ...item, ...payload } : item));
  } else {
    houses.unshift({ id: crypto.randomUUID(), ...payload, createdAt: Date.now() });
  }
  saveToStorage();
  renderList();
}

function deleteHouse(id) {
  houses = houses.filter((item) => item.id !== id);
  saveToStorage();
  renderList();
}

houseForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const payload = {
    name: houseForm.name.value.trim(),
    address: houseForm.address.value.trim(),
    area: houseForm.area.value,
    status: houseForm.status.value,
    note: houseForm.note.value.trim()
  };
  if (!payload.name || !payload.address) return;
  upsertHouse(payload);
  closeForm();
});

houseListEl.addEventListener('click', (e) => {
  const target = e.target.closest('button');
  if (!target) return;
  const { action, id } = target.dataset;
  const item = houses.find((h) => h.id === id);
  if (action === 'edit' && item) {
    openForm(item);
    return;
  }
  if (action === 'delete' && item) {
    if (window.confirm(`确认删除 ${item.name} 吗？`)) {
      deleteHouse(id);
    }
  }
});

searchInput.addEventListener('input', renderList);
statusFilter.addEventListener('change', renderList);
addBtn.addEventListener('click', () => openForm());
cancelBtn.addEventListener('click', closeForm);

loadFromStorage();
renderList();
