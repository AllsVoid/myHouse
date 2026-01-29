# 学区地图数据处理系统

本项目用于将政府文件中的学区/施教区描述自动转为结构化数据，并生成可在地图中查看的多边形范围。

## 功能概览
- 多格式解析：PDF/图片/Word/Excel -> 纯文本
- LLM 结构化提取：纯文本 -> 结构化 JSON
- 粗略多边形生成：JSON -> GeoJSON（高德地理编码 + bbox 草稿）
- 前后端分离：Vue 前端 + FastAPI API
- 房屋管理：表单录入、图片上传/粘贴、多图预览与看房地图

## 目录结构
- `app/data_trans`：文件解析与 LLM 结构化
- `app/web`：FastAPI API 服务
- `data/files`：原始文件
- `data/outputs`：解析后的纯文本
- `data/json`：LLM 结构化结果
- `data/polygons`：生成的 GeoJSON 多边形
- `scripts`：辅助脚本（导入 PostGIS、手动索引更新等）
- `frontend`：Vue 前端

## 快速开始
### 1) 解析原始文件
```bash
python main.py update
```

### 2) LLM 转换为 JSON
```bash
python main.py transform
```

### 3) 生成粗略多边形
```bash
python main.py polygon --key <AMAP_KEY>
```

### 4) 启动后端 API
```bash
uvicorn app.web.main:app --host 0.0.0.0 --port 8000
```

### 5) 启动前端 (Vue)
```bash
cd frontend
pnpm install
pnpm dev
```

## GitHub Pages 部署
前端支持 GitHub Actions 构建并发布到 GitHub Pages。手动触发时可填写 API 地址，避免后续改代码。

### 触发方式
在 GitHub Actions 中手动运行 `Deploy Frontend to GitHub Pages`：
- `api_base_url`：后端 API 地址（例如 `https://api.example.com`）
- `page_base`：Pages 基路径（默认 `/<repo>/`）

### 工作流位置
`.github/workflows/deploy-pages.yml`

## 环境变量
- `ARK_API_KEY`：火山引擎 Ark LLM API Key
- `API_BASE_URL`：后端 API 地址（用于前端配置下发）
- `AMAP_KEY`：高德 Web 服务 API Key（用于地理编码）
- `AMAP_JS_KEY`：高德 JS API Key（用于前端地图）
- `AMAP_SECURITY_JS_CODE`：高德安全密钥（如已开通）
- `FRONTEND_ORIGINS`：前端地址白名单（逗号分隔，默认 `http://localhost:5173`）

## 说明
- `polygon` 生成的是草稿多边形，用于快速预览，后续建议人工修正。
- 坐标系当前不做转换，前端直接使用原始坐标渲染。