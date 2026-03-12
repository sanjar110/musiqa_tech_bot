import psutil
import GPUtil
import tkinter as tk
from tkinter import ttk

def update_stats():
    # CPU
    cpu_load = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq().current
    cpu_label.config(text=f"CPU: {cpu_load}% | {cpu_freq:.0f} MHz")

    # RAM
    ram = psutil.virtual_memory()
    ram_label.config(text=f"RAM: {ram.percent}% | {ram.used//(1024**3)}GB/{ram.total//(1024**3)}GB")

    # Disk
    disk = psutil.disk_usage('/')
    disk_label.config(text=f"Disk: {disk.percent}% | {disk.used//(1024**3)}GB/{disk.total//(1024**3)}GB")

    # GPU
    gpus = GPUtil.getGPUs()
    if gpus:
        gpu = gpus[0]
        gpu_label.config(text=f"GPU: {gpu.load*100:.1f}% | {gpu.temperature}°C | "
                              f"{gpu.memoryUsed}MB/{gpu.memoryTotal}MB")
    else:
        gpu_label.config(text="GPU: topilmadi")

    # Har 2 soniyada yangilash
    root.after(2000, update_stats)

# Oyna yaratish
root = tk.Tk()
root.title("Kompyuter Monitoring Gajeti")
root.geometry("400x200")

# Stil
style = ttk.Style()
style.configure("TLabel", font=("Arial", 12))

# Label bloklari
cpu_label = ttk.Label(root, text="CPU: ...")
cpu_label.pack(pady=5)

ram_label = ttk.Label(root, text="RAM: ...")
ram_label.pack(pady=5)

disk_label = ttk.Label(root, text="Disk: ...")
disk_label.pack(pady=5)

gpu_label = ttk.Label(root, text="GPU: ...")
gpu_label.pack(pady=5)

# Boshlash
update_stats()
root.mainloop()
