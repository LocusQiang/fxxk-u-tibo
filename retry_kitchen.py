"""Automatic Codex retry with parabolic kitchen throws and a one-second toast."""
import argparse
from collections import deque
import ctypes
import faulthandler
from ctypes import wintypes
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import queue
import random
import sys
import threading
import time
import tkinter as tk

from monitor import HERE, Journal, Scanner, Sender, AutoRetry
from overlay import LayeredOverlay, message_image
from kitchen_art import KitchenArt, Flight, Toast
from desktop_state import desktop_available
from lifecycle import acquire_mutex, close_mutex
from app_config import DATA_DIR, ensure_data_dir, translate

def flight_duration(pending):
    """Drain bursts without overlapping windows or shortening the one-second toast."""
    if pending >= 2:
        return 1.6
    if pending:
        return 2.6
    return random.uniform(3.6, 4.5)

class KitchenApp:
    def __init__(self, args, journal=None, desktop_check=desktop_available):
        self.args = args
        self.desktop_check = desktop_check
        self.visual_allowed = self.desktop_check()
        self.simulated = args.demo and journal is not None
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title('Codex 厨房重试')
        self.root.protocol('WM_DELETE_WINDOW', self.request_stop)
        self.scale = max(1, self.root.winfo_fpixels('1i')/96)
        self.art=KitchenArt(self.scale,None if args.demo else DATA_DIR/'kitchen-order.json')
        self.width=self.height=round(self.art.size*self.scale)
        self.projectile=LayeredOverlay(self.root,'Codex 厨房抛掷')
        self.message=LayeredOverlay(self.root,'Codex 重试次数')
        self.events, self.notifications = queue.Queue(), deque()
        self.stop = threading.Event()
        self.paused = threading.Event()
        self.active = None
        self.frames, self.positions, self.text_positions = 0, [], []
        self.toast_hide_time=None
        self.toast_job=None
        self.toast_shown=None
        self.angle = 0.0
        self.started = 0
        self.journal = journal if journal is not None else Journal()
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label=translate('Pause / resume retries', '暂停 / 恢复自动重试'), command=self.toggle_pause)
        self.menu.add_command(label=translate('Open this conversation', '打开对应对话'), command=self.open_current)
        self.menu.add_command(label=translate('Stop auto retry', '退出自动重试'), command=self.request_stop)
        for overlay in (self.projectile,self.message):
            overlay.window.bind('<Button-3>', lambda e: self.menu.tk_popup(e.x_root,e.y_root))
            overlay.window.bind('<Escape>', lambda e: self.hide())
        if args.demo:
            for _ in range(args.demo_count):
                self.notifications.append({'kind':'sent', 'count':self.journal.daily_count(), 'title':'预览 · 不会发送消息'})
        else:
            self.worker = threading.Thread(target=self.watch, daemon=True)
            self.worker.start()
        self.root.after(30, self.animate)
        self.root.after(100, self.pump)
        if args.screenshot:
            self.root.after(800,self.screenshot)
        if args.ui_smoke:
            self.root.after(4700, self.smoke_check)

    def watch(self):
        scanner = Scanner()
        sender = Sender(scanner, self.journal, self.args.node)
        engine = AutoRetry(scanner, self.journal, sender, self.notify,
                           stopped=lambda: self.stop.is_set() or self.paused.is_set())
        last_error = None
        baseline_ready = False
        while not self.stop.is_set():
            if not self.paused.is_set():
                try:
                    if not baseline_ready:
                        self.journal.initialize_baseline(scanner)
                        baseline_ready = True
                    engine.tick()
                    last_error = None
                except Exception as error:
                    if str(error) != last_error:
                        logging.exception('Monitor failed; retrying in 2 seconds')
                        last_error = str(error)
            self.stop.wait(2)

    def notify(self, notification):
        # Capture visibility at confirmation time, even if the UI is delayed.
        # The sending worker never waits for the animation or for unlock.
        show_visual = self.desktop_check()
        if not show_visual:
            logging.info('Visual skipped while desktop unavailable thread=%s kind=%s count=%s',
                         notification.get('thread_id'), notification['kind'], notification.get('count'))
        self.events.put({**notification, 'show_visual': show_visual})

    def pump(self):
        if not self.args.demo and (DATA_DIR / 'stop.request').exists():
            self.quit()
            return
        available = self.desktop_check()
        if available != self.visual_allowed:
            logging.info('Desktop available=%s; automatic sending remains enabled unless paused', available)
        self.visual_allowed = available
        if not available:
            # Discard visual backlog only; confirmed sends and daily counts stay durable.
            self.notifications.clear()
            if self.active or self.projectile.visible or self.message.visible:
                self.hide()
        try:
            while True:
                notification = self.events.get_nowait()
                if available and notification.get('show_visual', True):
                    self.notifications.append(notification)
        except queue.Empty:
            pass
        self.root.after(100, self.pump)

    def toggle_pause(self):
        if self.paused.is_set():
            self.paused.clear()
        else:
            self.paused.set()
        logging.info('Automatic retry paused=%s', self.paused.is_set())

    def open_current(self):
        if self.active and self.active.get('thread_id') and not self.args.demo:
            os.startfile('codex://threads/' + self.active['thread_id'])

    def work_area(self):
        rect = wintypes.RECT()
        if not ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):
            raise ctypes.WinError()
        return rect

    def begin(self, notification):
        self.active = notification
        self.started = time.monotonic()
        self.rect = self.work_area()
        self.duration = 3.3 if self.args.ui_smoke else flight_duration(len(self.notifications))
        self.flight = Flight(self.rect.left, self.rect.top, self.rect.right, self.rect.bottom,
                             self.width, self.height, self.scale)
        unknown=notification['kind']=='unknown'
        message = translate('Send unconfirmed. Check conversation.', '发送结果未确认，请检查对话') if unknown else translate(
            f'Retried again! #{notification["count"]} today.', f'又重试啦，今天的第{notification["count"]}次。')
        if self.simulated:
            message='并发测试 · '+message
        self.message_art=message_image(message,self.scale,unknown)
        self.toast=Toast(self.rect.left,self.rect.top,self.rect.right,self.rect.bottom,
                         *self.message_art.size,self.scale)
        self.item=None if unknown else self.art.choose()
        self.toast_hide_time=None
        if unknown:
            self.duration = 1.05
        else:
            logging.info('Kitchen throw item=%s demo=%s thread=%s count=%s queued=%s duration=%.1f',
                         self.item['id'],self.args.demo,notification.get('thread_id'),
                         notification.get('count'),len(self.notifications),self.duration)
        self.place(0)
        self.render(0)
        self.message.show(self.message_art,*self.text_position)
        self.toast_shown=time.monotonic()
        self.toast_job=self.root.after(1000,self.hide_toast)

    def place(self, progress):
        x,y,self.angle=self.flight.point(progress)
        self.projectile_position=(x,y)
        self.text_position=self.toast.position
        if self.args.ui_smoke:
            self.positions.append((x,y))
            self.text_positions.append(self.text_position)

    def render(self, elapsed):
        if self.item:
            self.projectile.show(self.art.frame(self.angle),*self.projectile_position)

    def hide_toast(self):
        if self.toast_job:
            self.root.after_cancel(self.toast_job)
            self.toast_job=None
        if self.message.visible:
            self.message.hide()
            self.toast_hide_time=time.monotonic()-self.toast_shown

    def animate(self):
        try:
            self.animate_frame()
        except Exception:
            # A desktop switch can race a frame; keep the UI loop recoverable.
            logging.exception('Animation frame failed; automatic sending is independent')
            self.hide()
            self.root.after(100, self.animate)

    def animate_frame(self):
        if not self.visual_allowed:
            if self.args.demo and not self.args.ui_smoke and not self.notifications:
                self.quit()
                return
            self.root.after(100, self.animate)
            return
        if not self.active and self.notifications:
            self.begin(self.notifications.popleft())
        if self.active:
            elapsed = time.monotonic()-self.started
            progress = min(1,elapsed/self.duration)
            self.place(progress)
            self.render(elapsed)
            self.frames += 1
            if progress >= 1:
                self.hide()
                if self.args.demo and not self.args.ui_smoke and not self.notifications:
                    self.quit()
                    return
        self.root.after(16 if self.active else 100,self.animate)

    def hide(self):
        self.active = None
        self.projectile.hide()
        self.hide_toast()

    def screenshot(self):
        from PIL import ImageGrab
        self.root.update_idletasks()
        bounds=[o.bounds for o in (self.projectile,self.message) if o.visible]
        if not bounds:
            return
        x=max(self.rect.left,min(b[0] for b in bounds))
        y=max(self.rect.top,min(b[1] for b in bounds))
        right=min(self.rect.right,max(b[2] for b in bounds))
        bottom=min(self.rect.bottom,max(b[3] for b in bounds))
        ImageGrab.grab(bbox=(x,y,right,bottom),all_screens=True,include_layered_windows=True).save(self.args.screenshot)

    def smoke_check(self):
        assert self.frames > 20
        assert self.positions[0][0] > self.positions[-1][0]
        assert all(a[0]>=b[0] for a,b in zip(self.positions,self.positions[1:]))
        assert max(y for x,y in self.positions)-min(y for x,y in self.positions)>20
        ys=[y for x,y in self.positions]
        assert min(ys)<min(ys[0],ys[-1])-50
        assert len(set(self.text_positions))==1
        assert self.toast_hide_time is not None and .90<=self.toast_hide_time<=1.15
        assert not self.active and not any(o.user32.IsWindowVisible(o.hwnd) for o in (self.projectile,self.message))
        print(json.dumps({'ui_smoke':'passed','parabolic_right_to_left':True,'toast_stationary':True,
                          'toast_seconds':round(self.toast_hide_time,3),'item':self.item['name'],
                          'frames':self.frames,'demo_only':True,'daily_count':self.journal.daily_count()},ensure_ascii=False),flush=True)
        self.quit()

    def request_stop(self):
        if not self.args.demo:
            (DATA_DIR / 'stop.request').write_text('manual stop', encoding='utf-8')
        self.quit()

    def quit(self):
        if self.stop.is_set():
            return
        logging.info('Shutdown requested pid=%s demo=%s manual_stop=%s',
                     os.getpid(), self.args.demo, (DATA_DIR / 'stop.request').exists())
        self.stop.set()
        self.hide()
        self.finish_shutdown()

    def finish_shutdown(self):
        worker = getattr(self, 'worker', None)
        if worker is not None and worker.is_alive():
            self.root.after(100, self.finish_shutdown)
            return
        self.projectile.close()
        self.message.close()
        self.root.destroy()

def main():
    if sys.platform != 'win32':
        raise SystemExit('Codex Auto Retry Kitchen requires Windows 10/11 and Codex Desktop.')
    parser=argparse.ArgumentParser()
    parser.add_argument('--node',default='node')
    parser.add_argument('--demo',action='store_true')
    parser.add_argument('--demo-count',type=int,default=1)
    parser.add_argument('--scan',action='store_true')
    parser.add_argument('--ui-smoke',action='store_true')
    parser.add_argument('--screenshot')
    args=parser.parse_args()
    if args.scan:
        print(json.dumps({'pending':len(Scanner().scan()),'daily_count':Journal().daily_count()},ensure_ascii=False))
        return
    args.demo=args.demo or args.ui_smoke
    if not args.demo and (DATA_DIR / 'stop.request').exists():
        return
    args.demo_count=1 if args.ui_smoke else max(1,min(28,args.demo_count))
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    handle=None if args.demo else acquire_mutex()
    if not args.demo and not handle:
        return
    ensure_data_dir()
    logging.basicConfig(level=logging.INFO,handlers=[RotatingFileHandler(DATA_DIR/'auto-retry.log',maxBytes=1048576,backupCount=2,encoding='utf-8')],format='%(asctime)s %(levelname)s %(message)s')
    crash_output = (DATA_DIR / 'native-crash.log').open('a', encoding='utf-8')
    faulthandler.enable(file=crash_output, all_threads=True)
    def thread_failed(args):
        logging.critical('Background thread failed', exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        logging.shutdown()
        os._exit(1)  # Let the supervisor restore monitoring instead of silently losing it.
    threading.excepthook = thread_failed
    try:
        if not args.demo:
            (DATA_DIR/'auto-retry.pid').write_text(str(os.getpid()),encoding='ascii')
        logging.info('Started pid=%s demo=%s',os.getpid(),args.demo)
        KitchenApp(args).root.mainloop()
        logging.info('Main loop ended pid=%s manual_stop=%s', os.getpid(), (DATA_DIR / 'stop.request').exists())
    except Exception:
        logging.exception('Fatal error')
        raise
    finally:
        faulthandler.disable()
        crash_output.close()
        if handle:
            (DATA_DIR/'auto-retry.pid').unlink(missing_ok=True)
            close_mutex(handle)

if __name__=='__main__':
    main()
