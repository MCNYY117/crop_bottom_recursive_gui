#!/usr/bin/env python3
"""
crop_bottom_recursive_gui.py

图形界面批量裁剪图片底部（保留顶部指定高度）。
支持递归遍历输入目录下的所有子目录，并在输出目录中保持相同目录结构。
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from PIL import Image


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
        self.ext_var = tk.StringVar(value=".jpg .jpeg .png .bmp .tiff")

        # 标志
        self.processing = False
        self.log_queue = []

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
        extensions = [e.strip() for e in ext_str.split() if e.strip()] if ext_str else [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]

        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, "开始处理...\n")
        self.log_queue.clear()

        self.processing = True
        thread = threading.Thread(
            target=self.process_images,
            args=(input_dir, output_dir, crop_y, extensions),
            daemon=True
        )
        thread.start()
        self.update_log()

    def process_images(self, input_root, output_root, crop_y, extensions):
        """递归遍历 input_root 下所有子目录，裁剪图片并保持目录结构"""
        try:
            # 先尝试读取第一张图片校验裁剪高度
            sample_file = None
            for root, dirs, files in os.walk(input_root):
                for f in files:
                    if os.path.splitext(f)[1].lower() in extensions:
                        sample_file = os.path.join(root, f)
                        break
                if sample_file:
                    break

            if not sample_file:
                self.log_queue.append("没有找到任何匹配扩展名的图片文件。")
                return

            try:
                with Image.open(sample_file) as img:
                    width, height = img.size
                    if crop_y > height:
                        self.log_queue.append(f"错误：裁剪 Y 坐标 ({crop_y}) 超出图片高度 ({height})，请调整。")
                        return
            except Exception as e:
                self.log_queue.append(f"读取示例图片失败: {e}")
                return

            processed = 0
            total_files = 0

            # 遍历所有子目录
            for root, dirs, files in os.walk(input_root):
                for filename in files:
                    if os.path.splitext(filename)[1].lower() not in extensions:
                        continue

                    total_files += 1
                    input_path = os.path.join(root, filename)

                    # 计算相对路径
                    rel_path = os.path.relpath(input_path, input_root)
                    if output_root:
                        # 构建输出完整路径
                        output_path = os.path.join(output_root, rel_path)
                        # 确保输出子目录存在
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    else:
                        # 覆盖原文件
                        output_path = input_path

                    try:
                        with Image.open(input_path) as img:
                            cropped = img.crop((0, 0, img.width, crop_y))
                            cropped.save(output_path)
                        self.log_queue.append(f"✓ 已裁剪: {rel_path} (新高度 {crop_y})")
                    except Exception as e:
                        self.log_queue.append(f"✗ 处理失败 {rel_path}: {e}")
                    processed += 1

            self.log_queue.append(f"\n处理完成，共裁剪 {processed} 张图片。")
        except Exception as e:
            self.log_queue.append(f"错误: {e}")
        finally:
            self.processing = False

    def update_log(self):
        while self.log_queue:
            msg = self.log_queue.pop(0)
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)

        if self.processing:
            self.root.after(100, self.update_log)
        else:
            if self.log_queue:
                self.root.after(100, self.update_log)
            else:
                self.log_text.insert(tk.END, "\n[全部完成]")
                self.log_text.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = CropBottomApp(root)
    root.mainloop()