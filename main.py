#!/usr/bin/env python3
"""
学区地图数据处理系统 - 主入口
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List

from app.data_trans import DataTrans

# 配置常量
INPUT_DIR = Path("data/files")
OUTPUT_DIR = Path("data/outputs")
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


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(
        description="学区地图数据处理系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py update              # 解析所有文件
  python main.py update --dry-run    # 预览模式，不实际执行
  python main.py update -v           # 详细输出模式
  python main.py update_single_file <file_path> # 更新单个文件
  python main.py update_single_file --dry-run <file_path> # 预览模式，不实际执行
  python main.py update_single_file -v <file_path> # 详细输出模式
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # update 子命令
    update_parser = subparsers.add_parser(
        "update", help="扫描并解析 data/files 目录下的所有文件"
    )
    update_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，只显示将要处理的文件，不实际执行",
    )
    update_parser.add_argument(
        "-v", "--verbose", action="store_true", help="输出详细信息"
    )

    # update_single_file 子命令
    single_parser = subparsers.add_parser("update_single_file", help="更新单个文件")
    single_parser.add_argument("file_path", type=Path, help="要处理的文件路径")
    single_parser.add_argument(
        "-v", "--verbose", action="store_true", help="输出详细信息"
    )

    args = parser.parse_args()

    if args.command == "update":
        update(dry_run=args.dry_run, verbose=args.verbose)
    elif args.command == "update_single_file":
        update_single_file(args.file_path, verbose=args.verbose)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
