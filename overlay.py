"""Native transparent overlay windows and one-second retry toast artwork."""
import ctypes
from ctypes import wintypes
import math
import os
from pathlib import Path
import tkinter as tk
from PIL import Image, ImageDraw, ImageFilter, ImageFont
INK = '#253D54'

def toast_font(size):
    fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    for name in ('msyhbd.ttc', 'msyh.ttc', 'simhei.ttf', 'segoeuib.ttf', 'arialbd.ttf'):
        try:
            return ImageFont.truetype(str(fonts / name), size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)

def message_image(message, scale, unknown=False):
    ratio=scale*2
    font=toast_font(round(15*ratio))
    width=math.ceil(font.getlength(message)/ratio)+70
    height=68
    image=Image.new('RGBA',(round(width*ratio),round(height*ratio)))
    draw=ImageDraw.Draw(image)
    box=tuple(round(v*ratio) for v in (5,8,width-5,58))
    draw.rounded_rectangle((box[0],box[1]+3*ratio,box[2],box[3]+4*ratio),radius=24*ratio,fill=(17,32,52,42))
    image=image.filter(ImageFilter.GaussianBlur(3*ratio))
    draw=ImageDraw.Draw(image)
    draw.rounded_rectangle(box,radius=24*ratio,fill=(250,251,247,249),outline=(205,222,224,255),width=round(ratio))
    draw.ellipse(tuple(round(v*ratio) for v in (21,26,33,38)),fill='#EF836F' if not unknown else '#E3AC59')
    draw.ellipse(tuple(round(v*ratio) for v in (24,28,27,31)),fill='#FFE6CE')
    draw.text((43*ratio,31*ratio),message,font=font,fill=INK,anchor='lm')
    return image.resize((round(width*scale),round(height*scale)),Image.Resampling.LANCZOS)


class LayeredOverlay:
    """Tk event handling plus native alpha compositing; never activates on show."""
    def __init__(self, root, title):
        self.window=tk.Toplevel(root)
        self.window.withdraw()
        self.window.title(title)
        self.window.overrideredirect(True)
        self.window.attributes('-toolwindow',True)
        self.window.update_idletasks()
        self.user32=ctypes.WinDLL('user32',use_last_error=True)
        self.gdi32=ctypes.WinDLL('gdi32',use_last_error=True)
        self.user32.GetParent.argtypes=(wintypes.HWND,)
        self.user32.GetParent.restype=wintypes.HWND
        self.hwnd=self.user32.GetParent(self.window.winfo_id())
        self.user32.GetWindowLongW.argtypes=(wintypes.HWND,ctypes.c_int)
        self.user32.SetWindowLongW.argtypes=(wintypes.HWND,ctypes.c_int,ctypes.c_long)
        self.user32.SetWindowLongW(self.hwnd,-20,self.user32.GetWindowLongW(self.hwnd,-20)|0x08080080)
        self.user32.SetWindowPos.argtypes=(wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT)
        self.user32.ShowWindow.argtypes=(wintypes.HWND,ctypes.c_int)
        self.user32.IsWindowVisible.argtypes=(wintypes.HWND,)
        self.gdi32.CreateCompatibleDC.argtypes=(wintypes.HDC,)
        self.gdi32.CreateCompatibleDC.restype=wintypes.HDC
        self.gdi32.SelectObject.argtypes=(wintypes.HDC,wintypes.HANDLE)
        self.gdi32.SelectObject.restype=wintypes.HANDLE
        self.gdi32.DeleteObject.argtypes=(wintypes.HANDLE,)
        self.gdi32.DeleteDC.argtypes=(wintypes.HDC,)
        self.dc=self.gdi32.CreateCompatibleDC(None)
        self.bitmap=None
        self.previous=None
        self.size=None
        self.bounds=None
        self.visible=False

    def show(self, image, x, y):
        class Header(ctypes.Structure):
            _fields_=[('size',wintypes.DWORD),('width',wintypes.LONG),('height',wintypes.LONG),
                      ('planes',wintypes.WORD),('bits',wintypes.WORD),('compression',wintypes.DWORD),
                      ('image_size',wintypes.DWORD),('xppm',wintypes.LONG),('yppm',wintypes.LONG),
                      ('used',wintypes.DWORD),('important',wintypes.DWORD)]
        class Blend(ctypes.Structure):
            _fields_=[('op',ctypes.c_ubyte),('flags',ctypes.c_ubyte),('alpha',ctypes.c_ubyte),('format',ctypes.c_ubyte)]
        if self.size!=image.size:
            if self.bitmap:
                self.gdi32.SelectObject(self.dc,self.previous)
                self.gdi32.DeleteObject(self.bitmap)
            self.size=image.size
            header=Header(ctypes.sizeof(Header),image.width,-image.height,1,32,0,0,0,0,0,0)
            self.bits=ctypes.c_void_p()
            self.gdi32.CreateDIBSection.argtypes=(wintypes.HDC,ctypes.c_void_p,wintypes.UINT,ctypes.POINTER(ctypes.c_void_p),wintypes.HANDLE,wintypes.DWORD)
            self.gdi32.CreateDIBSection.restype=wintypes.HANDLE
            self.bitmap=self.gdi32.CreateDIBSection(self.dc,ctypes.byref(header),0,ctypes.byref(self.bits),None,0)
            if not self.bitmap:
                raise ctypes.WinError(ctypes.get_last_error())
            self.previous=self.gdi32.SelectObject(self.dc,self.bitmap)
        # Windows ULW_ALPHA expects premultiplied BGRA, including the soft edges.
        premult=image.convert('RGBa')
        r,g,b,a=premult.split()
        pixels=Image.merge('RGBA',(b,g,r,a)).tobytes()
        ctypes.memmove(self.bits,pixels,len(pixels))
        target=wintypes.POINT(round(x),round(y))
        origin=wintypes.POINT(0,0)
        size=wintypes.SIZE(*image.size)
        blend=Blend(0,0,255,1)
        self.user32.UpdateLayeredWindow.argtypes=(wintypes.HWND,wintypes.HDC,ctypes.POINTER(wintypes.POINT),ctypes.POINTER(wintypes.SIZE),wintypes.HDC,ctypes.POINTER(wintypes.POINT),wintypes.DWORD,ctypes.POINTER(Blend),wintypes.DWORD)
        if not self.user32.UpdateLayeredWindow(self.hwnd,None,ctypes.byref(target),ctypes.byref(size),self.dc,ctypes.byref(origin),0,ctypes.byref(blend),2):
            raise ctypes.WinError(ctypes.get_last_error())
        self.bounds=(target.x,target.y,target.x+image.width,target.y+image.height)
        if not self.visible:
            self.user32.SetWindowPos(self.hwnd,wintypes.HWND(-1),0,0,0,0,0x13)
            self.user32.ShowWindow(self.hwnd,4)
            self.visible=True

    def hide(self):
        self.user32.ShowWindow(self.hwnd,0)
        self.visible=False

    def close(self):
        self.hide()
        if self.bitmap:
            self.gdi32.SelectObject(self.dc,self.previous)
            self.gdi32.DeleteObject(self.bitmap)
        self.gdi32.DeleteDC(self.dc)
        self.window.destroy()
