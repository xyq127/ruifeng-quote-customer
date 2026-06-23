#!/usr/bin/env python3
"""图片识别封装 —— 从个人配置取 SiliconFlow Key，调 qwen-vision 识别配件编号。

把「读取个人配置里的 qwen-vision Key」+「调用 qwen-vision 的 vision.py」+
「业务定制识别 prompt」三件事封装成一条命令，工作流无需重复拼 prompt / 处理 Key。

Key 解析顺序：环境变量 SILICONFLOW_API_KEY → 个人配置文件（personal_config）。
vision.py 路径：环境变量 QWEN_VISION_SCRIPT → ~/.claude → ~/.hermes 下的安装位置。

用法:
  python recognize_image.py --image-path bearing.jpg            # 默认 OE/编号识别
  python recognize_image.py --image-path quote.png --mode quote # 报价单逐行 OCR
  python recognize_image.py --image-path x.jpg --prompt "自定义"
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from personal_config import get_siliconflow_key  # noqa: E402
from ruifeng_platform import first_run_hint  # noqa: E402

# 业务定制 prompt：单件编号识别 / 报价单逐行 OCR
PROMPTS = {
    "oe": (
        "识别图中汽车轴承/配件的所有编号文字：OE号、工厂编号(DAC/DU/RAH等)、钢印号、"
        "品牌(SKF/NSK/FAG/NTN/KOYO)关联编号、包装盒型号、尺寸(如45x84x45)。"
        "逐条列出原文并标注每个编号的疑似类型；钢印/实物编号优先。"
        "看不清的标注'模糊'，不要臆造。"
    ),
    "quote": (
        "逐行识别这张汽车配件报价单：每行的编号/OE号、名称、车型、数量、价格，"
        "按表格原样列出，看不清的标注'模糊'，不要臆造。"
    ),
}


def _resolve_vision_script() -> str:
    cand = [os.environ.get("QWEN_VISION_SCRIPT")]
    cand += [str(Path.home() / base / "skills" / "qwen-vision" / "scripts" / "vision.py")
             for base in (".claude", ".hermes")]
    for c in cand:
        if c and Path(c).is_file():
            return c
    sys.exit("未找到 qwen-vision 的 vision.py。请确认已安装 qwen-vision skill，"
             "或用环境变量 QWEN_VISION_SCRIPT 指定其路径。")


def main():
    parser = argparse.ArgumentParser(description="调 qwen-vision 识别配件图片中的编号")
    parser.add_argument("--image-path", required=True, help="图片本地路径或 URL")
    parser.add_argument("--mode", choices=list(PROMPTS), default="oe",
                        help="oe=单件编号识别（默认）；quote=报价单逐行 OCR")
    parser.add_argument("--prompt", help="自定义提示词（覆盖 --mode 默认）")
    parser.add_argument("--output", choices=["text", "json"], default="text")
    parser.add_argument("--model", help="覆盖默认视觉模型")
    args = parser.parse_args()

    key = get_siliconflow_key()
    if not key:
        sys.exit(first_run_hint("qwen-vision 的 SiliconFlow API Key")
                 + "\n获取 Key：https://cloud.siliconflow.cn/")

    vision = _resolve_vision_script()
    prompt = args.prompt or PROMPTS[args.mode]
    cmd = [sys.executable, vision, "--image-path", args.image_path,
           "--output", args.output, "--prompt", prompt]
    if args.model:
        cmd += ["--model", args.model]

    env = dict(os.environ, SILICONFLOW_API_KEY=key)
    os.execvpe(sys.executable, cmd, env)  # 交棒给 vision.py，输出/退出码透传


if __name__ == "__main__":
    main()
