"""Native local-only statistics and controls. Closing this window keeps retries on."""
import json
import os
from pathlib import Path
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk
from app_config import ROOT, DATA_DIR, app_command, codex_home, runtime_settings, language, translate as tr
from lifecycle import mutex_exists
from retry_stats import summarize

BG, INK, MUTED, GREEN, AMBER = '#F5F2E9', '#233A36', '#5C6B67', '#237568', '#A56120'


def font(size, bold=False):
    return ('Microsoft YaHei UI' if language() == 'zh' else 'Segoe UI', -round(size * 1.2), 'bold' if bold else 'normal')


def spawn(*args):
    env = {**os.environ, 'PYINSTALLER_RESET_ENVIRONMENT': '1'}
    return subprocess.Popen(app_command(*args), env=env, creationflags=subprocess.CREATE_NO_WINDOW)


class Dashboard:
    def __init__(self, root):
        self.root = root
        root.title('fxxk u tibo · ' + tr('Retry statistics', '重试统计'))
        root.configure(bg=BG)
        root.geometry('940x760')
        root.minsize(800, 700)
        self.days = tk.IntVar(value=30)
        self.job = None
        self.closed = False
        self.status = tk.StringVar()
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('Treeview', font=font(11), rowheight=30, background='#FFFFFF',
                        fieldbackground='#FFFFFF', foreground=INK, borderwidth=0)
        style.configure('Treeview.Heading', font=font(10, True), background='#E7EBE4', foreground=INK)
        style.map('Treeview', background=[('selected', GREEN)], foreground=[('selected', 'white')])
        header = tk.Frame(root, bg=BG)
        header.pack(fill='x', padx=30, pady=(22, 12))
        art = Image.open(ROOT / 'assets/kitchen/sprites/frying-pan.png').convert('RGBA')
        art.thumbnail((76, 76))
        self.icon = ImageTk.PhotoImage(art)
        root.iconphoto(True, self.icon)
        tk.Label(header, image=self.icon, bg=BG).pack(side='left', padx=(0, 12))
        heading = tk.Frame(header, bg=BG)
        heading.pack(side='left')
        self.label(heading, tr('A little retry kitchen', '重试小厨房'), 23, True).pack(anchor='w')
        self.label(heading, tr('Daily activity, kept on this computer.', '每天的重试，都记在这台电脑里。'), 11, color=MUTED).pack(anchor='w', pady=(5, 0))
        tk.Label(header, textvariable=self.status, bg=BG, fg=GREEN, font=font(11, True)).pack(side='right')
        metrics = tk.Frame(root, bg=BG)
        metrics.pack(fill='x', padx=30, pady=(0, 18))
        self.values = []
        for title, color in [(tr('Today', '今天已重试'), GREEN), (tr('Selected period', '所选时段'), INK),
                             (tr('All time', '累计已重试'), INK), (tr('Unconfirmed · all time', '待确认 · 累计'), AMBER)]:
            box = tk.Frame(metrics, bg='white', padx=18, pady=12)
            box.pack(side='left', expand=True, fill='both', padx=(0, 8))
            self.label(box, title, 10, color=MUTED, bg='white').pack(anchor='w')
            value = self.label(box, '—', 30, True, color=color, bg='white')
            value.pack(anchor='w')
            self.values.append(value)
        filters = tk.Frame(root, bg=BG)
        filters.pack(fill='x', padx=30)
        self.label(filters, tr('Daily trend', '每日趋势'), 14, True).pack(side='left')
        for days in (90, 30, 7):
            tk.Radiobutton(filters, text=tr(f'{days} days', f'{days} 天'), variable=self.days, value=days,
                           command=self.refresh, bg=BG, fg=INK, selectcolor='#DDE9E1',
                           font=font(11), indicatoron=False, relief='flat', padx=14, pady=5).pack(side='right', padx=3)
        self.chart = tk.Canvas(root, bg=BG, height=175, highlightthickness=0)
        self.chart.pack(fill='x', padx=30, pady=(4, 5))
        self.chart.bind('<Configure>', lambda event: self.draw_chart() if hasattr(self, 'report') else None)
        self.label(root, tr('Green: confirmed sends  ·  Amber: unconfirmed  ·  Local calendar dates',
                            '绿色：已确认启动   ·   橙色：待确认   ·   按本机日期统计'), 10, color=MUTED).pack(anchor='w', padx=30)
        table = tk.Frame(root, bg=BG)
        table.pack(fill='both', expand=True, padx=30, pady=(12, 8))
        self.table = ttk.Treeview(table, columns=('day', 'sent', 'unknown', 'chats'), show='headings', height=3)
        for key, title in zip(('day', 'sent', 'unknown', 'chats'),
                              (tr('Date', '日期'), tr('Confirmed', '已重试'), tr('Unconfirmed', '待确认'), tr('Conversations', '涉及对话'))):
            self.table.heading(key, text=title)
            self.table.column(key, width=170, anchor='center')
        scroll = ttk.Scrollbar(table, orient='vertical', command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.note = tk.StringVar()
        tk.Label(root, textvariable=self.note, bg=BG, fg=MUTED, font=font(10), anchor='w').pack(fill='x', padx=30)
        controls = tk.Frame(root, bg=BG)
        controls.pack(fill='x', padx=30, pady=(12, 6))
        self.button(controls, tr('Start retries', '启动重试'), self.start, primary=True).pack(side='left')
        self.button(controls, tr('Stop', '停止'), self.stop).pack(side='left', padx=6)
        self.button(controls, tr('Preview', '预览动画'), lambda: spawn('--preview')).pack(side='left')
        self.button(controls, tr('Logon startup…', '开机自启动…'), self.autostart).pack(side='right')
        self.button(controls, tr('Codex folder…', 'Codex 目录…'), self.configure).pack(side='right', padx=6)
        self.label(root, tr('Counts confirm a new turn started, not that the task succeeded. Closing this window keeps retries running.',
                            '次数代表新轮次已确认启动，不代表任务成功。关闭统计窗口不会停止重试。'), 10, color=MUTED).pack(anchor='w', padx=30, pady=(0, 14))
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.refresh()

    def label(self, parent, text, size, bold=False, color=INK, bg=BG):
        return tk.Label(parent, text=text, font=font(size, bold), bg=bg, fg=color)

    def button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, font=font(10), relief='flat',
                         bg=GREEN if primary else '#E3E8DF', fg='white' if primary else INK, padx=12, pady=8)

    def refresh(self):
        if self.job:
            self.root.after_cancel(self.job)
        try:
            self.report = summarize(DATA_DIR / 'actions.jsonl', self.days.get())
            for label, value in zip(self.values, (self.report[k] for k in ('today', 'period', 'total', 'unknown'))):
                label.configure(text=f'{value:,}')
            yview = self.table.yview()
            self.table.delete(*self.table.get_children())
            for row in reversed(self.report['days']):
                self.table.insert('', 'end', values=[row[k] for k in ('date', 'sent', 'unknown', 'chats')])
            self.table.yview_moveto(yview[0])
            self.note.set(tr('Updates every 5 seconds · Unconfirmed sends are never resent automatically.',
                             '每 5 秒刷新 · 未确认的发送不会自动重发。') +
                          (tr(f' Skipped {self.report["malformed"]} unreadable rows.', f' 已跳过 {self.report["malformed"]} 条无效记录。') if self.report['malformed'] else ''))
            self.draw_chart()
            running = mutex_exists()
            own = (DATA_DIR / 'auto-retry.pid').exists()
            stopping = (DATA_DIR / 'stop.request').exists()
            self.status.set(tr('● Running', '● 运行中') if running and own and not stopping else
                            tr('○ Stopping', '○ 正在停止') if running and own else
                            tr('○ Another installation is running', '○ 其他安装正在运行') if running else
                            tr('○ Stopped', '○ 已停止'))
        except (OSError, ValueError) as error:
            self.note.set(tr('Cannot read local statistics: ', '无法读取本地统计：') + str(error))
        self.job = self.root.after(5000, self.refresh)

    def draw_chart(self):
        c = self.chart
        c.delete('all')
        width = max(300, c.winfo_width())
        left, right, top, bottom = 42, width - 12, 16, 143
        rows = self.report['days']
        peak = max(2, max(row['sent'] + row['unknown'] for row in rows))
        peak += peak % 2
        for fraction in (0, .5, 1):
            y = bottom - fraction * (bottom - top)
            c.create_line(left, y, right, y, fill='#D9DFD5')
            c.create_text(left - 8, y, text=f'{peak * fraction:g}', anchor='e', fill=MUTED, font=font(9))
        step = (right - left) / len(rows)
        for i, row in enumerate(rows):
            x = left + i * step + step * .16
            y = bottom - row['sent'] / peak * (bottom - top)
            if row['sent']:
                c.create_rectangle(x, y, x + step * .68, bottom, fill=GREEN, width=0)
            if row['unknown']:
                c.create_rectangle(x, y - row['unknown'] / peak * (bottom - top), x + step * .68, y, fill=AMBER, width=0)
            if i in (0, len(rows) // 2, len(rows) - 1):
                c.create_text(x + step * .34, bottom + 17, text=row['date'][5:], fill=MUTED, font=font(9))
        if not any(row['sent'] or row['unknown'] for row in rows):
            c.create_text(width // 2, 72, text=tr('No retries in this period', '这个时段还没有重试记录'), fill=MUTED, font=font(13))

    def start(self):
        from doctor import schema_check
        errors = [row for row in schema_check(codex_home()) if row['status'] != 'ok']
        if errors:
            messagebox.showerror(tr('Check Codex folder', '请检查 Codex 目录'),
                                 tr('Compatible Codex history was not found. Choose the Codex folder first.', '未找到兼容的 Codex 历史数据库，请先选择 Codex 目录。'), parent=self.root)
            return
        spawn('--start')
        self.root.after(1500, self.refresh)

    def stop(self):
        (DATA_DIR / 'stop.request').write_text('manual stop', encoding='utf-8')
        self.root.after(1500, self.refresh)

    def configure(self):
        if mutex_exists():
            messagebox.showinfo('Codex', tr('Stop retries before changing the folder.', '请先停止重试，再修改目录。'), parent=self.root)
            return
        chosen = filedialog.askdirectory(parent=self.root, initialdir=codex_home(), title=tr('Choose CODEX_HOME', '选择 CODEX_HOME 目录'))
        if chosen:
            marker = DATA_DIR / 'baseline.json'
            if marker.exists() and os.path.normcase(str(Path(chosen).resolve())) != json.loads(marker.read_text(encoding='utf-8'))['codex_home']:
                messagebox.showerror('Codex', tr('This journal belongs to another Codex folder. Use a separate data directory; history was preserved.',
                                                '此记录属于其他 Codex 目录，请使用独立的数据目录。已有记录已保留。'), parent=self.root)
                return
            settings = runtime_settings()
            settings['codex_home'] = str(Path(chosen).resolve())
            path = DATA_DIR / 'runtime.json'
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(path)

    def autostart(self):
        from startup import change_autostart, autostart_installed
        try:
            enabled = autostart_installed()
            prompt = tr('Disable startup at sign-in?', '关闭开机登录自启动？') if enabled else tr(
                'Enable startup at sign-in and recovery every minute? Monitoring may start within one minute.',
                '启用开机登录自启动和每分钟故障恢复？可能在一分钟内开始监测。')
            if messagebox.askyesno(tr('Logon startup', '开机自启动'), prompt, parent=self.root):
                change_autostart(remove=enabled)
                messagebox.showinfo('fxxk u tibo', tr('Startup disabled.', '已关闭自启动。') if enabled else tr('Startup enabled.', '已开启自启动。'), parent=self.root)
        except Exception as error:
            messagebox.showerror('fxxk u tibo', str(error), parent=self.root)

    def close(self):
        self.closed = True
        if self.job:
            self.root.after_cancel(self.job)
        self.root.destroy()
