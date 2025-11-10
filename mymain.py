import time
import random
import tkinter as tk
import math as mt
from dialgauge import dialgauge
from dialgauge2 import dialgauge2
from dialgauge3 import dialgauge3

 

root=tk.Tk()
#root.attributes('-fullscreen',True)
root.title("主窗口")

def gauge1buttonf():
    child_window = tk.Toplevel(root)
    #child_window.attributes('-fullscreen',True)
    child_window.title("子窗口")
    child_window.geometry("300x200")  # 设置子窗口大小

    mygauge=dialgauge(child_window)
    mygauge.drawbackground()
    mygauge.showcavnas()
    mygauge.update()

gauge1button=tk.Button(root,text="gauge1",command=gauge1buttonf).pack()



#child_window = tk.Toplevel(root)
#child_window.attributes('-fullscreen',True)
#child_window.title("子窗口")
#child_window.geometry("300x200")  # 设置子窗口大小
#mygauge=dialgauge(child_window)
#mygauge.drawbackground()
#mygauge.showcavnas()
def gauge2buttonf():

    child_window2=tk.Toplevel(root)

    child_window2.title("子窗口2")
    child_window2.geometry("300x200")  # 设置子窗口大小

    mygauge2=dialgauge2(child_window2)
    mygauge2.drawbackground()
    mygauge2.showcavnas()
    mygauge2.update()
gauge2button=tk.Button(root,text="gauge2",command=gauge2buttonf).pack()


def gauge3buttonf():
    child_window3 = tk.Toplevel(root)
    child_window3.title("子窗口3")
    child_window3.geometry("300x200")

    mygauge3 = dialgauge3(child_window3)
    mygauge3.drawbackground()
    mygauge3.showcavnas()
    mygauge3.update()
gauge3button=tk.Button(root,text="gauge3(digital)",command=gauge3buttonf).pack()
root.mainloop()
