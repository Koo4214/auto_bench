"""列出指定 OSS 前缀下所有对象的标签信息。"""

from __future__ import annotations

import sys
from pathlib import Path

# 将项目根目录加入路径，以便导入 src 模块
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.services.oss_upload_service import (
    OSS_ACCESS_KEY_ID,
    OSS_ACCESS_KEY_SECRET,
    OSS_BUCKET_NAME,
    OSS_ENDPOINT,
    OSS_PATH_PREFIX,
)


def main() -> None:
    try:
        import oss2
    except ImportError:
        print("错误: 未安装 oss2，请执行 pip install oss2")
        sys.exit(1)

    # 目标前缀从命令行参数获取，格式如：
    # benchmark_data/2026-04-23/ProbeVehicle_TEST001/042326_ProbeVehicle_TEST001_Run20260423_101104/
    if len(sys.argv) < 2:
        print("用法: python list_oss_tags.py <oss_prefix>")
        print("示例: python list_oss_tags.py benchmark_data/2026-04-23/ProbeVehicle_TEST001/042326_ProbeVehicle_TEST001_Run20260423_101104/")
        sys.exit(1)
    prefix = sys.argv[1]
    # 自动补全末尾 /
    if not prefix.endswith("/"):
        prefix += "/"

    auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)

    print(f"Bucket: {OSS_BUCKET_NAME}")
    print(f"Prefix: {prefix}")
    print("-" * 60)

    count = 0
    for obj in oss2.ObjectIterator(bucket, prefix=prefix):
        count += 1
        try:
            tagging_result = bucket.get_object_tagging(obj.key)
            # tagging_result.tag_set 是 TaggingRule 对象，
            # tagging_rule 属性为 dict {key: value}
            rules = tagging_result.tag_set.tagging_rule
            if rules:
                tag_str = ", ".join(f"{k}={v}" for k, v in rules.items())
            else:
                tag_str = "(无标签)"
        except Exception as e:
            tag_str = f"(获取标签失败: {e})"

        print(f"{obj.key}")
        print(f"  标签: {tag_str}")
        print()

    if count == 0:
        print("该前缀下未找到任何对象。")
    else:
        print(f"共 {count} 个对象。")


if __name__ == "__main__":
    main()
