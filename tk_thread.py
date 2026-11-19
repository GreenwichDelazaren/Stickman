"""Tk on a thread of its own, for the desktop's file dialogs and Document Composer window.

pygame and Tk can't share a thread on Windows: pygame.event.get() releases Python's lock while SDL
reads the thread's window messages, and Windows then hands it the Tk window's messages too, so Tk
runs Python callbacks without the lock and Python aborts ("PyEval_RestoreThread ... GIL is released").
Here every Tk call happens on the Tk thread, and what must happen on the main thread (OpenGL, the
editor's state) is sent back there:

  on_tk(fn, *args)    run fn on the Tk thread and return its result (or raise its exception)
  on_main(fn, *args)  run fn on the main thread, likewise; App.run calls run_main_calls() every frame

A thread waiting for the other keeps running the calls sent to it, so neither can deadlock (a dialog
the composer window opens through the main thread runs on the Tk thread meanwhile).

No pygame/OpenGL.
"""

import queue
import threading
import time

_root = None
_tk_thread = None
_main_thread = threading.main_thread()
_to_tk, _to_main = queue.Queue(), queue.Queue()
_ready = threading.Event()
error_handler = None  # fn(type, value, traceback): where exceptions in Tk callbacks go


def _run_calls(q):
    while True:
        try:
            fn, args, box = q.get_nowait()
        except queue.Empty:
            return
        try:
            box["result"] = fn(*args)
        except BaseException as exc:  # handed to the caller
            box["error"] = exc
        box["done"].set()


def _send(q, own, fn, args):
    box = {"done": threading.Event()}
    q.put((fn, args, box))
    while not box["done"].wait(0.005):
        if own is not None:
            _run_calls(own)  # the other side may need us meanwhile
    if "error" in box:
        raise box["error"]
    return box.get("result")


def _thread():
    global _root
    import tkinter as tk
    _root = tk.Tk()
    _root.withdraw()
    if error_handler is not None:
        _root.report_callback_exception = error_handler

    def poll():
        _run_calls(_to_tk)
        _root.after(10, poll)
    poll()
    _ready.set()
    _root.mainloop()


def start():
    global _tk_thread
    if _tk_thread is None:
        _tk_thread = threading.Thread(target=_thread, name="tk", daemon=True)
        _tk_thread.start()
        _ready.wait()


def root():
    """The Tk root (use it only on the Tk thread)."""
    return _root


def on_tk(fn, *args):
    start()
    if threading.current_thread() is _tk_thread:
        return fn(*args)
    return _send(_to_tk, _to_main if threading.current_thread() is _main_thread else None, fn, args)


def on_main(fn, *args):
    if threading.current_thread() is _main_thread:
        return fn(*args)
    return _send(_to_main, _to_tk if threading.current_thread() is _tk_thread else None, fn, args)


def run_main_calls():
    _run_calls(_to_main)


def stop():
    if _root is not None:
        _to_tk.put((_root.quit, (), {"done": threading.Event()}))
        time.sleep(0.05)


class MainProxy:
    """obj's methods, called from the Tk thread but run on the main thread."""

    def __init__(self, obj):
        self._obj = obj

    def __getattr__(self, name):
        attr = getattr(self._obj, name)
        return (lambda *args: on_main(attr, *args)) if callable(attr) else attr
