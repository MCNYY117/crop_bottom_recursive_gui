#!/usr/bin/env python3
"""
crop_bottom_recursive_gui.py

图形界面批量裁剪图片底部（保留顶部指定高度）。
支持递归遍历输入目录下的所有子目录，并在输出目录中保持相同目录结构。
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from PIL import Image


DEFAULT_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]


def collect_images(input_root, extensions):
    """递归收集所有匹配扩展名的图片，返回 [(绝对路径, 相对路径), ...]。"""
    found = []
    for root, _dirs, files in os.walk(input_root):
        for name in files:
            if os.path.splitext(name)[1].lower() in extensions:
                full = os.path.join(root, name)
                found.append((full, os.path.relpath(full, input_root)))
    return found


def read_height(path):
    """只读文件头拿高度 —— Pillow 的 open 是惰性的，不会解码整张图。

    读不出来（损坏、不是图片、没权限）返回 None，交给裁剪那一步去报具体错误。
    """
    try:
        with Image.open(path) as img:
            return img.height
    except Exception:
        return None


def crop_one(src, dst, crop_y):
    """裁剪一张图并保存到 dst，返回 (是否成功, 说明文字)。

    两个刻意的细节：

    1. **先把像素解出来、把文件关掉，再往磁盘写。** 覆盖模式下 src == dst，
       如果还在 `Image.open` 的 with 块里就往同一个路径写，源文件句柄还开着 ——
       在 Windows 上这种行为不可靠。

    2. **尽量不重新压缩。** JPEG 把原图的量化表（quantization tables）原样搬过去，
       裁剪因此不产生第二代损失；EXIF 也一并透传。搬不了（格式不支持、缺表）
       就退回默认保存 —— 那样至少文件是好的。
    """
    try:
        # 目标目录由本函数自己保证 —— 不然「写文件」这件事就带着一个
        # 调用方必须记住的隐含前提，漏一次就是 FileNotFoundError
        parent = os.path.dirname(dst)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with Image.open(src) as img:
            if crop_y > img.height:
                # 不钳位、不补边：静默补一圈黑边比直接报错更糟 ——
                # 用户会以为处理成功了，直到肉眼看出问题
                return False, f"高度仅 {img.height}px，不足裁剪线 {crop_y}px"

            save_kwargs = {}
            exif = img.info.get("exif")
            if exif:
                save_kwargs["exif"] = exif
            qtables = getattr(img, "quantization", None)
            if qtables:
                save_kwargs["qtables"] = dict(qtables)

            cropped = img.crop((0, 0, img.width, crop_y))
            cropped.load()

        try:
            cropped.save(dst, **save_kwargs)
        except Exception:
            # qtables / exif 不是每种格式都吃，退回默认保存也比整张失败强
            cropped.save(dst)
        return True, ""
    except Exception as exc:
        return False, str(exc)


class CropBottomApp:
    def __init__(self, root):
        self.root = root
        root.title("批量裁剪图片底部（支持子目录） - 图形界面")
        root.geometry("720x580")
        root.resizable(True, True)

        # 变量
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.crop_y_var = tk.StringVar()
        self.ext_var = tk.StringVar(value=" ".join(DEFAULT_EXTENSIONS))

        # 标志
        self.processing = False
        # 真正线程安全的队列。原来用的是普通 list：工作线程 append、主线程 pop，
        # 靠 GIL 侥幸没出事，但那不是保证。
        self.log_queue = queue.Queue()

        self.create_widgets()

    def create_widgets(self):
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        row = 0

        # 输入目录
        tk.Label(main_frame, text="输入根目录：", anchor="e", width=14).grid(row=row, column=0, sticky="e", pady=5)
        tk.Entry(main_frame, textvariable=self.input_var, width=50).grid(row=row, column=1, sticky="ew", padx=5)
        tk.Button(main_frame, text="浏览...", command=self.browse_input).grid(row=row, column=2, padx=5)
        row += 1

        # 输出目录
        tk.Label(main_frame, text="输出根目录：", anchor="e", width=14).grid(row=row, column=0, sticky="e", pady=5)
        tk.Entry(main_frame, textvariable=self.output_var, width=50).grid(row=row, column=1, sticky="ew", padx=5)
        tk.Button(main_frame, text="浏览...", command=self.browse_output).grid(row=row, column=2, padx=5)
        row += 1
        tk.Label(main_frame, text="（留空则覆盖原文件，将递归覆盖所有子目录中的原图，请谨慎操作）",
                 fg="gray", font=("Arial", 9)).grid(row=row, column=1, sticky="w", pady=(0, 10))
        row += 1

        # 裁剪 Y 坐标
        coord_frame = tk.Frame(main_frame)
        coord_frame.grid(row=row, column=0, columnspan=3, pady=10, sticky="w")
        tk.Label(coord_frame, text="裁剪起始 Y 坐标（保留顶部 0 ~ Y-1 行）：").pack(side=tk.LEFT, padx=(0, 10))
        tk.Entry(coord_frame, textvariable=self.crop_y_var, width=8).pack(side=tk.LEFT)
        row += 1
        tk.Label(main_frame, text="坐标原点为图片左上角 (0,0)，向下Y增加。", fg="gray", font=("Arial", 9)).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(0, 5)
        )
        row += 1

        # 扩展名
        tk.Label(main_frame, text="文件扩展名：", anchor="e", width=14).grid(row=row, column=0, sticky="e", pady=5)
        tk.Entry(main_frame, textvariable=self.ext_var, width=50).grid(row=row, column=1, sticky="ew", padx=5)
        tk.Label(main_frame, text="（空格分隔）", fg="gray", font=("Arial", 9)).grid(
            row=row, column=2, sticky="w", padx=5
        )
        row += 1

        # 处理按钮
        btn_process = tk.Button(main_frame, text="开始裁剪", command=self.start_processing,
                                bg="#4CAF50", fg="white", font=("Arial", 12), height=1, width=20)
        btn_process.grid(row=row, column=0, columnspan=3, pady=20)
        row += 1

        # 日志
        tk.Label(main_frame, text="处理日志：", anchor="w").grid(row=row, column=0, columnspan=3, sticky="w")
        row += 1
        self.log_text = scrolledtext.ScrolledText(main_frame, height=15, state="normal", wrap=tk.WORD)
        self.log_text.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=(5, 0))

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(row, weight=1)

    def browse_input(self):
        d = filedialog.askdirectory()
        if d:
            self.input_var.set(d)

    def browse_output(self):
        d = filedialog.askdirectory()
        if d:
            self.output_var.set(d)

    def start_processing(self):
        if self.processing:
            messagebox.showinfo("提示", "正在处理中，请稍候...")
            return

        input_dir = self.input_var.get().strip()
        if not input_dir or not os.path.isdir(input_dir):
            messagebox.showerror("错误", "请输入有效的输入根目录")
            return

        output_dir = self.output_var.get().strip()
        if not output_dir:
            if not messagebox.askyesno("警告", "未指定输出目录，将直接覆盖原文件（包括所有子目录中的文件）！\n是否继续？"):
                return

        try:
            crop_y = int(self.crop_y_var.get())
        except ValueError:
            messagebox.showerror("错误", "裁剪 Y 坐标必须为整数")
            return

        if crop_y <= 0:
            messagebox.showerror("错误", "裁剪 Y 坐标必须大于 0")
            return

        ext_str = self.ext_var.get().strip()
        extensions = [e.strip().lower() for e in ext_str.split() if e.strip()] if ext_str else list(DEFAULT_EXTENSIONS)

        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, "开始处理...\n")
        # 换一个新队列，而不是清空旧的 —— 工作线程拿到的一定是干净的那一个
        self.log_queue = queue.Queue()

        self.processing = True
        thread = threading.Thread(
            target=self.process_images,
            args=(input_dir, output_dir, crop_y, extensions),
            daemon=True
        )
        thread.start()
        self.update_log()

    def process_images(self, input_root, output_root, crop_y, extensions):
        """递归遍历 input_root 下所有子目录，裁剪图片并保持目录结构。"""
        try:
            targets = collect_images(input_root, extensions)
            if not targets:
                self.log_queue.put("没有找到任何匹配扩展名的图片文件。")
                return

            # 预检：先把每张图的宽高读一遍（只读文件头，很快）。
            # 任何一张比裁剪线矮就整批不开工 —— 否则会处理到一半才失败，
            # 输出目录里留下半成品，而用户以为全部完成了。
            self.log_queue.put(f"共找到 {len(targets)} 张图片，正在检查高度...")
            too_short = []
            unreadable = []
            for path, rel in targets:
                height = read_height(path)
                if height is None:
                    unreadable.append(rel)
                elif crop_y > height:
                    too_short.append((rel, height))

            if too_short:
                self.log_queue.put(
                    f"错误：有 {len(too_short)} 张图片的高度小于裁剪线 {crop_y}px，未开始处理。"
                )
                for rel, height in too_short[:10]:
                    self.log_queue.put(f"    {rel} —— {height}px")
                if len(too_short) > 10:
                    self.log_queue.put(f"    ……还有 {len(too_short) - 10} 张")
                self.log_queue.put("请把裁剪起始 Y 调到不超过最矮那张图片的高度，然后重试。")
                return

            if unreadable:
                self.log_queue.put(
                    f"提示：{len(unreadable)} 个文件读不出尺寸，将在处理时逐个报错。"
                )

            done = 0
            failed = []

            for path, rel in targets:
                # 输出目录的创建交给 crop_one —— 谁写文件谁保证目录存在
                dest = os.path.join(output_root, rel) if output_root else path

                ok, why = crop_one(path, dest, crop_y)
                if ok:
                    done += 1
                    self.log_queue.put(f"✓ 已裁剪: {rel}")
                else:
                    failed.append(rel)
                    self.log_queue.put(f"✗ 失败 {rel}: {why}")

            summary = f"\n处理完成：成功 {done} 张"
            if failed:
                summary += f"，失败 {len(failed)} 张"
            summary += f"（共 {len(targets)} 张）。"
            self.log_queue.put(summary)
        except Exception as e:
            self.log_queue.put(f"错误: {e}")
        finally:
            self.processing = False

    def update_log(self):
        """把队列里的日志搬进文本框。只在主线程调用（由 root.after 驱动）。"""
        while True:
            try:
                msg = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)

        if self.processing:
            self.root.after(100, self.update_log)
        else:
            self.log_text.insert(tk.END, "\n[全部完成]")
            self.log_text.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = CropBottomApp(root)
    root.mainloop()
