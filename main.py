#!/usr/bin/env python3
"""
学区地图数据处理系统 - 主入口
"""

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

from app.data_trans import DataTrans
from app.data_trans.ai import Ai, LLMParseError

# 配置常量
INPUT_DIR = Path("data/files")
OUTPUT_DIR = Path("data/outputs")
JSON_DIR = Path("data/json")
OUTPUT_FORMAT = ".txt"  # 输出文件格式 (纯文本内容)


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

    args = parser.parse_args()

    if args.command == "update":
        update(dry_run=args.dry_run, verbose=args.verbose)
    elif args.command == "transform":
        transform(dry_run=args.dry_run, verbose=args.verbose)
    elif args.command == "update_single":
        update_single_file(args.file_path, verbose=args.verbose)
    elif args.command == "transform_single":
        transform_single_file(args.file_path, verbose=args.verbose, force=args.force)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
