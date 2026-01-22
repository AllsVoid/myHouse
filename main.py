#!/usr/bin/env python3
"""
学区地图数据处理系统 - 主入口
"""

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.data_trans import DataTrans
from app.data_trans.ai import Ai, LLMParseError

# 配置常量
INPUT_DIR = Path("data/files")
OUTPUT_DIR = Path("data/outputs")
JSON_DIR = Path("data/json")
OUTPUT_FORMAT = ".txt"  # 输出文件格式 (纯文本内容)
POLYGON_DIR = Path("data/polygons")
GEOCODE_CACHE = Path("data/.geocode_cache.json")
DEFAULT_CITY = "苏州"
REQUEST_INTERVAL_SEC = 0.2
POINTS_DIR = Path("data/polygons/points")
ITEM_POLYGON_DIR = Path("data/polygons/items")


def get_all_files(directory: Path) -> List[Path]:
    """
    递归获取目录下所有支持的文件

    Args:
        directory: 目录路径

    Returns:
        文件路径列表
    """
    supported_exts = set(DataTrans.get_supported_extensions())
    files = []

    for file_path in directory.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in supported_exts:
            files.append(file_path)

    return sorted(files)


def generate_output_filename(input_path: Path) -> str:
    """
    生成输出文件名

    规则: 原文件名(去掉扩展名) + OUTPUT_FORMAT
    例如: "2025 园区小学施教区.pdf" -> "2025 园区小学施教区.json"

    Args:
        input_path: 输入文件路径

    Returns:
        输出文件名
    """
    return input_path.stem + OUTPUT_FORMAT


def update(dry_run: bool = False, verbose: bool = False) -> None:
    """
    执行 update 操作：扫描并解析所有文件

    Args:
        dry_run: 如果为 True，只打印将要处理的文件，不实际执行
        verbose: 是否输出详细信息
    """
    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 获取所有待处理文件
    files = get_all_files(INPUT_DIR)

    if not files:
        print(f"[WARN] 未在 {INPUT_DIR} 目录下找到任何支持的文件")
        print(f"       支持的格式: {', '.join(DataTrans.get_supported_extensions())}")
        return

    print(f"[INPUT]  {INPUT_DIR}")
    print(f"[OUTPUT] {OUTPUT_DIR}")
    print(f"[TOTAL]  {len(files)} 个文件待处理")
    print("-" * 60)

    if dry_run:
        print("[DRY-RUN] 将要处理的文件:")
        for f in files:
            output_name = generate_output_filename(f)
            print(f"   {f.relative_to(INPUT_DIR)} -> {output_name}")
        return

    # 初始化解析器
    trans = DataTrans()

    # 统计
    success_count = 0
    fail_count = 0
    results_summary = []

    for i, file_path in enumerate(files, 1):
        output_name = generate_output_filename(file_path)
        output_path = OUTPUT_DIR / output_name

        # 处理文件名冲突 (不同目录下可能有同名文件)
        if output_path.exists():
            # 添加父目录名作为前缀
            parent_name = file_path.parent.name
            output_name = f"{parent_name}_{output_name}"
            output_path = OUTPUT_DIR / output_name

        print(f"[{i}/{len(files)}] 处理: {file_path.relative_to(INPUT_DIR)}")

        try:
            # 解析文件
            result = trans.process(file_path)

            if result.get("success"):
                # 只保存 content 内容
                content = result.get("content", "")
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(content)

                success_count += 1
                if verbose:
                    content_preview = content[:100] if content else ""
                    print(f"   [OK] -> {output_name}")
                    print(f"        预览: {content_preview}...")
                else:
                    print(f"   [OK] -> {output_name}")
            else:
                fail_count += 1
                print(f"   [FAIL] -> {output_name}")
                print(f"          错误: {result.get('error')}")

            results_summary.append(
                {
                    "input": str(file_path),
                    "output": str(output_path),
                    "success": result.get("success", False),
                    "error": result.get("error"),
                }
            )

        except Exception as e:
            fail_count += 1
            print(f"   [FAIL] 处理失败: {e}")
            results_summary.append(
                {
                    "input": str(file_path),
                    "output": None,
                    "success": False,
                    "error": str(e),
                }
            )

    # 打印统计
    print("-" * 60)
    print(f"[DONE] 成功 {success_count}, 失败 {fail_count}, 共 {len(files)}")

    # 保存处理摘要
    summary_path = OUTPUT_DIR / "_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total": len(files),
                "success": success_count,
                "failed": fail_count,
                "results": results_summary,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"[SUMMARY] {summary_path}")


def update_single_file(file_path: Path, verbose: bool = False) -> None:
    """
    更新单个文件

    Args:
        file_path: 文件路径
        verbose: 是否输出详细信息
    """
    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 生成输出文件名
    output_name = generate_output_filename(file_path)
    output_path = OUTPUT_DIR / output_name

    print(f"[INPUT]  {file_path}")
    print(f"[OUTPUT] {output_path}")
    print("-" * 60)

    trans = DataTrans()
    try:
        result = trans.process(file_path)

        if result.get("success"):
            # 只保存 content 内容
            content = result.get("content", "")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"[OK] -> {output_name}")
            if verbose:
                content_preview = content[:200] if content else ""
                print(f"     预览: {content_preview}...")
        else:
            print(f"[FAIL] 解析失败")
            print(f"       错误: {result.get('error')}")

    except Exception as e:
        print(f"[FAIL] 处理失败: {e}")


def transform(dry_run: bool = False, verbose: bool = False) -> None:
    """
    执行 transform 操作：调用 AI 将 data/outputs 中的文本转换为结构化 JSON

    Args:
        dry_run: 如果为 True，只打印将要处理的文件，不实际执行
        verbose: 是否输出详细信息
    """
    # 确保输出目录存在
    JSON_DIR.mkdir(parents=True, exist_ok=True)

    # 获取所有待处理的 txt 文件
    txt_files = sorted(OUTPUT_DIR.glob("*.txt"))
    # 排除 _summary.json 等特殊文件
    txt_files = [f for f in txt_files if not f.name.startswith("_")]

    if not txt_files:
        print(f"[WARN] 未在 {OUTPUT_DIR} 目录下找到任何 .txt 文件")
        print(f"       请先执行 'python main.py update' 解析源文件")
        return

    print(f"[INPUT]  {OUTPUT_DIR}")
    print(f"[OUTPUT] {JSON_DIR}")
    print(f"[TOTAL]  {len(txt_files)} 个文件待转换")
    print("-" * 60)

    if dry_run:
        print("[DRY-RUN] 将要处理的文件:")
        for f in txt_files:
            json_name = f.stem + ".json"
            print(f"   {f.name} -> {json_name}")
        return

    # 初始化 AI
    try:
        ai = Ai()
    except Exception as e:
        print(f"[FAIL] AI 初始化失败: {e}")
        return

    # 统计
    success_count = 0
    fail_count = 0
    results_summary = []
    start_time = time.time()

    for i, txt_file in enumerate(txt_files, 1):
        json_name = txt_file.stem + ".json"
        json_path = JSON_DIR / json_name

        # 检查是否已存在
        if json_path.exists():
            if verbose:
                print(f"{progress} 跳过: {txt_file.name} (JSON 已存在)")
            else:
                # 即使跳过也需要保持进度显示的一致性或者静默
                pass

            results_summary.append(
                {
                    "input": str(txt_file),
                    "output": str(json_path),
                    "success": True,
                    "skipped": True,
                    "error": None,
                }
            )
            continue

        # 进度显示
        elapsed = time.time() - start_time
        avg_time = elapsed / i if i > 1 else 0
        remaining = avg_time * (len(txt_files) - i)
        progress = f"[{i}/{len(txt_files)}]"
        time_info = f"(已用 {elapsed:.0f}s, 剩余约 {remaining:.0f}s)" if i > 1 else ""

        print(f"{progress} 处理: {txt_file.name} {time_info}")

        try:
            # 读取文本内容
            content = txt_file.read_text(encoding="utf-8")
            content_len = len(content)

            if verbose:
                print(f"       文本长度: {content_len} 字符")

            # 使用流式提取并边生成边写入
            school_count = 0

            with open(json_path, "w", encoding="utf-8") as f:
                # 写入头部
                f.write("{\n")
                f.write(f'  "source_file": "{txt_file.name}",\n')
                f.write('  "schools": [\n')

                first = True
                try:
                    # 调用流式接口
                    for school in ai.extract_geo_info_stream(content, verbose=verbose):
                        if not first:
                            f.write(",\n")

                        # 序列化单个对象并缩进
                        school_str = json.dumps(school, ensure_ascii=False, indent=4)
                        # 增加缩进
                        school_str = "    " + school_str.replace("\n", "\n    ")
                        f.write(school_str)
                        f.flush()  # 确保写入磁盘

                        school_count += 1
                        first = False
                except Exception as stream_e:
                    print(f"       [WARN] 流式处理中断: {stream_e}")
                    # 不重新抛出，视为部分成功

                # 写入尾部
                f.write("\n  ],\n")
                f.write(f'  "school_count": {school_count}\n')
                f.write("}")

            success_count += 1
            print(f"       [OK] -> {json_name} (提取到 {school_count} 个学校)")

            if verbose and school_count > 0:
                pass  # 已经在流式中打印了

            results_summary.append(
                {
                    "input": str(txt_file),
                    "output": str(json_path),
                    "success": True,
                    "school_count": school_count,
                    "error": None,
                }
            )

        except Exception as e:
            fail_count += 1
            print(f"       [FAIL] {e}")
            results_summary.append(
                {
                    "input": str(txt_file),
                    "output": None,
                    "success": False,
                    "school_count": 0,
                    "error": str(e),
                }
            )

        # 请求间隔，避免触发限流
        if i < len(txt_files):
            time.sleep(0.5)

    # 打印统计
    total_time = time.time() - start_time
    print("-" * 60)
    print(f"[DONE] 成功 {success_count}, 失败 {fail_count}, 共 {len(txt_files)}")
    print(
        f"[TIME] 总耗时 {total_time:.1f}s, 平均 {total_time/len(txt_files):.1f}s/文件"
    )

    # 保存处理摘要
    summary_path = JSON_DIR / "_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total": len(txt_files),
                "success": success_count,
                "failed": fail_count,
                "total_time_seconds": round(total_time, 2),
                "results": results_summary,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"[SUMMARY] {summary_path}")


def transform_single_file(
    file_path: Path, verbose: bool = False, force: bool = False
) -> None:
    """
    转换单个文件

    Args:
        file_path: 文本文件路径
        verbose: 是否输出详细信息
        force: 是否强制覆盖已存在的 JSON
    """
    # 确保输出目录存在
    JSON_DIR.mkdir(parents=True, exist_ok=True)

    # 生成输出文件名
    json_name = file_path.stem + ".json"
    json_path = JSON_DIR / json_name

    if json_path.exists() and not force:
        print(f"[WARN] 目标文件已存在: {json_path}")
        print(f"       使用 --force 参数覆盖")
        return

    print(f"[INPUT]  {file_path}")
    print(f"[OUTPUT] {json_path}")
    print("-" * 60)

    try:
        # 读取文本内容
        content = file_path.read_text(encoding="utf-8")
        content_len = len(content)
        print(f"[INFO] 文本长度: {content_len} 字符")

        # 初始化 AI 并提取
        ai = Ai()
        # 传递 verbose 参数，以便控制 stream
        geo_data = ai.extract_geo_info(content, verbose=verbose)

        if not geo_data:
            print(f"[WARN] 未提取到任何数据")

        # 保存结果
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "source_file": file_path.name,
                    "school_count": len(geo_data),
                    "schools": geo_data,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        if not json_path.exists():
            print(f"[ERR] 文件写入失败，未找到: {json_path}")
        else:
            print(f"[OK] -> {json_name} (提取到 {len(geo_data)} 个学校)")

        if verbose and geo_data:
            print(f"[PREVIEW] 前3个学校:")
            for school in geo_data[:3]:
                print(f"  - {school.get('school_name', 'N/A')}")

    except Exception as e:
        print(f"[FAIL] 处理失败: {e}")
        import traceback

        traceback.print_exc()


def load_geocode_cache() -> Dict[str, Tuple[float, float]]:
    if GEOCODE_CACHE.exists():
        return json.loads(GEOCODE_CACHE.read_text(encoding="utf-8"))
    return {}


def save_geocode_cache(cache: Dict[str, Tuple[float, float]]) -> None:
    GEOCODE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    GEOCODE_CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def geocode_amap(
    address: str,
    city: str,
    api_key: str,
    cache: Dict[str, Tuple[float, float]],
) -> Optional[Tuple[float, float]]:
    cache_key = f"{city}:{address}"
    if cache_key in cache:
        return tuple(cache[cache_key])

    params = {"key": api_key, "address": address, "city": city}
    url = f"https://restapi.amap.com/v3/geocode/geo?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if data.get("status") != "1" or not data.get("geocodes"):
        return None

    location = data["geocodes"][0].get("location")
    if not location:
        return None

    lng_str, lat_str = location.split(",")
    lng, lat = float(lng_str), float(lat_str)
    cache[cache_key] = (lng, lat)
    return lng, lat


def bbox_polygon(
    points: List[Tuple[float, float]], buffer_deg: float = 0.002
) -> Optional[List[List[float]]]:
    if not points:
        return None

    lngs = [p[0] for p in points]
    lats = [p[1] for p in points]
    min_lng, max_lng = min(lngs), max(lngs)
    min_lat, max_lat = min(lats), max(lats)

    if min_lng == max_lng and min_lat == max_lat:
        min_lng -= buffer_deg
        max_lng += buffer_deg
        min_lat -= buffer_deg
        max_lat += buffer_deg

    return [
        [min_lng, min_lat],
        [max_lng, min_lat],
        [max_lng, max_lat],
        [min_lng, max_lat],
        [min_lng, min_lat],
    ]


def hull_polygon(
    points: List[Tuple[float, float]],
    method: str = "convex",
    concave_ratio: float = 0.5,
) -> Optional[List[List[float]]]:
    if len(points) < 3:
        return bbox_polygon(points)

    try:
        from shapely.geometry import MultiPoint
    except Exception:
        return bbox_polygon(points)

    geom = MultiPoint(points)
    hull = None

    if method == "concave":
        try:
            from shapely import concave_hull

            hull = concave_hull(geom, ratio=concave_ratio)
        except Exception:
            hull = None

    if hull is None:
        hull = geom.convex_hull

    if hull is None or hull.is_empty:
        return None

    if hull.geom_type == "Polygon":
        coords = list(hull.exterior.coords)
        return [[float(x), float(y)] for x, y in coords]

    if hull.geom_type == "MultiPolygon":
        # 选面积最大的面
        largest = max(hull.geoms, key=lambda g: g.area, default=None)
        if largest is None:
            return None
        coords = list(largest.exterior.coords)
        return [[float(x), float(y)] for x, y in coords]

    return None


def buffer_point_polygon(
    point: Tuple[float, float], radius_m: float = 300.0
) -> Optional[List[List[float]]]:
    try:
        from math import cos, radians

        from shapely.geometry import Point
    except Exception:
        return None

    lng, lat = point
    scale_lat = 111000.0
    scale_lng = 111000.0 * max(cos(radians(lat)), 1e-6)

    pt_m = Point(lng * scale_lng, lat * scale_lat)
    poly_m = pt_m.buffer(radius_m)
    if poly_m.is_empty:
        return None

    coords = list(poly_m.exterior.coords)
    return [[float(x / scale_lng), float(y / scale_lat)] for x, y in coords]


def polygonize(
    dry_run: bool = False,
    city: str = DEFAULT_CITY,
    api_key: Optional[str] = None,
    limit: Optional[int] = None,
    hull_method: str = "convex",
    concave_ratio: float = 0.5,
    item_buffer_m: float = 300.0,
) -> None:
    """
    将 data/json 的结构化结果转换为粗略 polygon GeoJSON
    """
    api_key = api_key or os.getenv("AMAP_KEY")
    if not api_key:
        print("[FAIL] 缺少 AMAP_KEY，请设置环境变量或使用 --key")
        return

    POLYGON_DIR.mkdir(parents=True, exist_ok=True)
    POINTS_DIR.mkdir(parents=True, exist_ok=True)
    ITEM_POLYGON_DIR.mkdir(parents=True, exist_ok=True)
    cache = load_geocode_cache()

    files = sorted(JSON_DIR.glob("*.json"))
    if limit:
        files = files[:limit]

    if not files:
        print(f"[WARN] 未在 {JSON_DIR} 找到任何 JSON 文件")
        return

    if dry_run:
        print("[DRY-RUN] 将要处理的文件:")
        for f in files:
            print(f"  - {f.name}")
        return

    for file_path in files:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        schools = data.get("schools", [])

        features = []
        point_features = []
        item_features = []
        for school in schools:
            boundary_points: List[Tuple[float, float]] = []
            include_points: List[Tuple[float, float]] = []

            for b in school.get("boundaries", []):
                name = b.get("name")
                if name:
                    pt = geocode_amap(name, city, api_key, cache)
                    if pt:
                        boundary_points.append(pt)
                        point_features.append(
                            {
                                "type": "Feature",
                                "properties": {
                                    "school_name": school.get("school_name"),
                                    "source_file": file_path.name,
                                    "kind": "boundary",
                                    "name": name,
                                },
                                "geometry": {"type": "Point", "coordinates": list(pt)},
                            }
                        )
                    time.sleep(REQUEST_INTERVAL_SEC)

            for inc in school.get("includes", []):
                name = inc.get("name")
                if name:
                    pt = geocode_amap(name, city, api_key, cache)
                    if pt:
                        include_points.append(pt)
                        point_features.append(
                            {
                                "type": "Feature",
                                "properties": {
                                    "school_name": school.get("school_name"),
                                    "source_file": file_path.name,
                                    "kind": "include",
                                    "name": name,
                                },
                                "geometry": {"type": "Point", "coordinates": list(pt)},
                            }
                        )
                        item_polygon = buffer_point_polygon(pt, radius_m=item_buffer_m)
                        if item_polygon:
                            item_features.append(
                                {
                                    "type": "Feature",
                                    "properties": {
                                        "school_name": school.get("school_name"),
                                        "source_file": file_path.name,
                                        "kind": "include_area",
                                        "name": name,
                                    },
                                    "geometry": {
                                        "type": "Polygon",
                                        "coordinates": [item_polygon],
                                    },
                                }
                            )
                    time.sleep(REQUEST_INTERVAL_SEC)

            if hull_method != "convex":
                print(
                    f"[WARN] hull 方式已固定为 convex，忽略 {hull_method} (file: {file_path.name})"
                )
            polygon = hull_polygon(
                include_points, method="convex", concave_ratio=concave_ratio
            )
            if not polygon:
                continue

            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "school_name": school.get("school_name"),
                        "source_file": file_path.name,
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [polygon],
                    },
                }
            )

        out_path = POLYGON_DIR / file_path.with_suffix(".geojson").name
        geojson = {"type": "FeatureCollection", "features": features}
        out_path.write_text(
            json.dumps(geojson, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[OK] 生成: {out_path.name} (features: {len(features)})")

        points_path = POINTS_DIR / file_path.with_suffix(".points.geojson").name
        points_geojson = {"type": "FeatureCollection", "features": point_features}
        points_path.write_text(
            json.dumps(points_geojson, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[OK] 输出点集: {points_path.name} (points: {len(point_features)})")

        items_path = ITEM_POLYGON_DIR / file_path.with_suffix(".items.geojson").name
        items_geojson = {"type": "FeatureCollection", "features": item_features}
        items_path.write_text(
            json.dumps(items_geojson, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[OK] 输出细分面: {items_path.name} (features: {len(item_features)})")

    index_path = POLYGON_DIR / "index.json"
    geojson_files = sorted([p.name for p in POLYGON_DIR.glob("*.geojson")])
    index_path.write_text(
        json.dumps(geojson_files, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] 更新索引: {index_path} (files: {len(geojson_files)})")

    save_geocode_cache(cache)


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(
        description="学区地图数据处理系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 第一步：解析源文件 (PDF/Word/Excel/图片) 为纯文本
  python main.py update              # 解析所有文件到 data/outputs/
  python main.py update --dry-run    # 预览模式

  # 第二步：调用 AI 转换为结构化 JSON
  python main.py transform           # 转换所有文本到 data/json/
  python main.py transform --dry-run # 预览模式
  python main.py transform -v        # 详细模式

  # 第三步：生成 polygon GeoJSON
  python main.py polygon             # data/json -> data/polygons
  python main.py polygon --dry-run   # 预览模式
  python main.py polygon --key <AMAP_KEY>

  # 单文件操作
  python main.py update_single <file_path>
  python main.py transform_single <file_path>
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # update 子命令
    update_parser = subparsers.add_parser(
        "update", help="解析 data/files 目录下的源文件为纯文本"
    )
    update_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，只显示将要处理的文件",
    )
    update_parser.add_argument(
        "-v", "--verbose", action="store_true", help="输出详细信息"
    )

    # transform 子命令
    transform_parser = subparsers.add_parser(
        "transform", help="调用 AI 将 data/outputs 中的文本转换为结构化 JSON"
    )
    transform_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，只显示将要处理的文件",
    )
    transform_parser.add_argument(
        "-v", "--verbose", action="store_true", help="输出详细信息"
    )
    transform_parser.add_argument(
        "-w", "--workers", type=int, default=4, help="并行工作线程数 (默认: 4)"
    )

    # update_single 子命令
    update_single_parser = subparsers.add_parser(
        "update_single", help="解析单个源文件为纯文本"
    )
    update_single_parser.add_argument("file_path", type=Path, help="源文件路径")
    update_single_parser.add_argument(
        "-v", "--verbose", action="store_true", help="输出详细信息"
    )

    # transform_single 子命令
    transform_single_parser = subparsers.add_parser(
        "transform_single", help="调用 AI 转换单个文本文件为 JSON"
    )
    transform_single_parser.add_argument("file_path", type=Path, help="文本文件路径")
    transform_single_parser.add_argument(
        "-v", "--verbose", action="store_true", help="输出详细信息"
    )
    transform_single_parser.add_argument(
        "-f", "--force", action="store_true", help="强制覆盖已存在的文件"
    )

    # polygon 子命令
    polygon_parser = subparsers.add_parser(
        "polygon", help="将 data/json 的结果生成粗略 polygon GeoJSON"
    )
    polygon_parser.add_argument(
        "--dry-run", action="store_true", help="预览模式，只显示将要处理的文件"
    )
    polygon_parser.add_argument(
        "--city", default=DEFAULT_CITY, help="地理编码城市 (默认: 苏州)"
    )
    polygon_parser.add_argument("--key", default=None, help="AMAP API Key")
    polygon_parser.add_argument("--limit", type=int, default=None, help="限制处理文件数")
    polygon_parser.add_argument(
        "--hull",
        choices=["bbox", "convex", "concave"],
        default="convex",
        help="多边形生成方式 (默认: convex)",
    )
    polygon_parser.add_argument(
        "--concave-ratio",
        type=float,
        default=0.5,
        help="凹包收缩比例(0-1，越小越贴边，默认 0.5)",
    )
    polygon_parser.add_argument(
        "--item-buffer-m",
        type=float,
        default=300.0,
        help="细分面缓冲半径(米, 默认 300)",
    )

    args = parser.parse_args()

    if args.command == "update":
        update(dry_run=args.dry_run, verbose=args.verbose)
    elif args.command == "transform":
        transform(dry_run=args.dry_run, verbose=args.verbose)
    elif args.command == "update_single":
        update_single_file(args.file_path, verbose=args.verbose)
    elif args.command == "transform_single":
        transform_single_file(args.file_path, verbose=args.verbose, force=args.force)
    elif args.command == "polygon":
        polygonize(
            dry_run=args.dry_run,
            city=args.city,
            api_key=args.key,
            limit=args.limit,
            hull_method=args.hull,
            concave_ratio=args.concave_ratio,
            item_buffer_m=args.item_buffer_m,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
