# 房屋管理前端 (Vue)

该前端为“房屋管理 + 看房地图”模块，配合后端 FastAPI API 使用。

## 启动
```bash
pnpm install
pnpm dev
```

## 功能
- 房屋管理：新增/编辑/删除，字段校验与列表筛选
- 图片处理：多图上传/粘贴、缩略图预览、大图查看（左右切换、缩放、旋转）
- 看房地图：加载后端 GeoJSON 点位，点击显示缩略信息

## 依赖后端 API
- `GET /api/config`：获取地图配置
- `GET /api/houses`：房源列表
- `POST /api/houses`：创建房源
- `PUT /api/houses/{id}`：更新房源
- `DELETE /api/houses/{id}`：删除房源
- `GET /api/houses/geojson`：房源地图点位

## 注意
- 地图功能依赖 `.env` 中的 `AMAP_JS_KEY`/`AMAP_SECURITY_JS_CODE`
- 默认通过 Vite 代理访问后端 `http://localhost:8000`
