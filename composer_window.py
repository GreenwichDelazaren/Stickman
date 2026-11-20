"""The desktop's Document Composer window (tkinter), beside the pygame window.

It shows composer.summary() and sends every button and field to composer_actions through the host
(main.App), which also renders the preview pictures with OpenGL, and saves and exports. The pages
are drawn from composer.layout() geometry, as the website's composer and the exports place them.
It lives on the Tk thread (tk_thread.py); host is a tk_thread.MainProxy, so its methods run on
the main thread, and the window keeps the Tk images it makes from the host's PNGs.
"""

import tkinter as tk
from tkinter import ttk

import composer
import ttf
from i18n import tr

BG, PANEL, TEXT, DIM, ACTIVE = "#191e26", "#262c36", "#ebeef2", "#96a0af", "#2e68c4"
PAGE_GAP = 14
MAX_PAGE = 2400  # pixels: the widest a page is drawn, however far it's zoomed (Tk images are memory)


class ComposerWindow:
    def __init__(self, root, host):
        self.host = host
        self.zoom, self.page_shown = 1.0, 0
        self.photos = {}          # (key, w, h) -> PhotoImage, kept alive while shown
        self.shown = True         # read by the main thread (the toolbar button)
        self.drag = None
        self.win = tk.Toplevel(root)
        self.win.title(tr("Document Composer"))
        width, height = 780, min(940, self.win.winfo_screenheight() - 80)
        self.win.geometry(f"{width}x{height}+{max(0, self.win.winfo_screenwidth() - width - 20)}+30")
        self.win.minsize(460, 500)
        self.win.configure(bg=BG)
        self.win.protocol("WM_DELETE_WINDOW", self.hide)
        self.win.bind("<Control-z>", lambda e: self.act("undo"))
        self.win.bind("<Control-y>", lambda e: self.act("redo"))
        self.win.bind("<Delete>", lambda e: self.act("delete") if self.focus_is_canvas() else None)
        style = ttk.Style(self.win)
        style.theme_use("clam")
        for name in ("TLabel", "TCheckbutton", "TFrame", "TLabelframe", "TLabelframe.Label"):
            style.configure(name, background=BG, foreground=TEXT)
        style.configure("TButton", background=PANEL, foreground=TEXT, borderwidth=0, padding=(8, 4))
        style.map("TButton", background=[("active", "#58637a"), ("disabled", BG)], foreground=[("disabled", "#555c66")])
        style.configure("Accent.TButton", background=ACTIVE)
        style.configure("Layout.TButton", padding=2)
        style.map("TCheckbutton", background=[("active", BG)])
        self.build()
        self.refresh()

    # --- plumbing --------------------------------------------------------------------

    def focus_is_canvas(self):
        return self.win.focus_get() is self.canvas

    def act(self, name, arg=None):
        self.host.composer_do(name, arg)

    def show(self):
        self.shown = True
        self.win.deiconify()
        self.win.lift()
        self.refresh()

    def hide(self):
        self.shown = False
        self.win.withdraw()

    @property
    def visible(self):
        return self.win.winfo_exists() and self.win.state() != "withdrawn"

    def rebuild(self):
        """After the language changed: every label anew."""
        for child in self.win.winfo_children():
            child.destroy()
        self.win.title(tr("Document Composer"))
        self.build()
        self.refresh()

    # --- widgets -----------------------------------------------------------------------

    def build(self):
        w = self.win
        head = ttk.Frame(w)
        head.pack(fill="x", padx=8, pady=(8, 4))
        self.doc_choice = ttk.Combobox(head, state="readonly", width=18)
        self.doc_choice.bind("<<ComboboxSelected>>", lambda e: self.act("choose", self.doc_choice.current()))
        self.doc_choice.pack(side="left")
        for label, cmd in ((tr("New"), lambda: self.act("new")), (tr("Open"), self.host.composer_open),
                           (tr("Save"), self.host.composer_save), (tr("Close"), lambda: self.act("close"))):
            ttk.Button(head, text=label, command=cmd).pack(side="left", padx=(4, 0))
        ttk.Button(head, text=tr("Export"), style="Accent.TButton", command=self.host.composer_export).pack(
            side="left", padx=(4, 0))

        # Settings.
        self.settings = ttk.LabelFrame(w, text=tr("Document settings"))
        self.settings.pack(fill="x", padx=8, pady=4)
        s = self.settings
        self.name_var = tk.StringVar()
        self.format_box = ttk.Combobox(s, state="readonly", width=20,
                                       values=[tr(composer.FORMAT_NAMES[f]) for f in composer.FORMATS])
        self.orient_box = ttk.Combobox(s, state="readonly", width=14, values=[tr("A4 portrait"), tr("A4 landscape")])
        self.mode_box = ttk.Combobox(s, state="readonly", width=20,
                                     values=[tr(composer.MODE_NAMES[m]) for m in composer.MODES])
        self.margin_var = tk.StringVar()
        name = ttk.Entry(s, textvariable=self.name_var, width=22)
        name.bind("<Return>", lambda e: self.act("rename", self.name_var.get()))
        name.bind("<FocusOut>", lambda e: self.act("rename", self.name_var.get()))
        margin = ttk.Spinbox(s, from_=composer.MARGINS[0], to=composer.MARGINS[1], increment=1, width=6,
                             textvariable=self.margin_var, command=self._margin)
        margin.bind("<Return>", lambda e: self._margin())
        margin.bind("<FocusOut>", lambda e: self._margin())
        self.format_box.bind("<<ComboboxSelected>>",
                             lambda e: self.act("set", ["format", composer.FORMATS[self.format_box.current()]]))
        self.orient_box.bind("<<ComboboxSelected>>",
                             lambda e: self.act("set", ["orientation", ("portrait", "landscape")[self.orient_box.current()]]))
        self.mode_box.bind("<<ComboboxSelected>>",
                           lambda e: self.act("set", ["mode", composer.MODES[self.mode_box.current()]]))
        rows = [(tr("Name"), name, tr("Format"), self.format_box),
                (tr("Page"), self.orient_box, tr("Margins (mm)"), margin)]
        for r, (l1, w1, l2, w2) in enumerate(rows):
            ttk.Label(s, text=l1, foreground=DIM).grid(row=r, column=0, sticky="w", padx=4, pady=2)
            w1.grid(row=r, column=1, sticky="w", padx=4, pady=2)
            ttk.Label(s, text=l2, foreground=DIM).grid(row=r, column=2, sticky="w", padx=4, pady=2)
            w2.grid(row=r, column=3, sticky="w", padx=4, pady=2)
        ttk.Label(s, text=tr("Figures go in as"), foreground=DIM).grid(row=2, column=0, sticky="w", padx=4)
        self.mode_box.grid(row=2, column=1, sticky="w", padx=4, pady=2)
        self.flags = {}
        images, captions = ttk.Frame(s), ttk.Frame(s)
        images.grid(row=2, column=2, columnspan=2, sticky="w", padx=2)
        captions.grid(row=3, column=0, columnspan=4, sticky="w", padx=2)
        ttk.Label(captions, text=tr("Captions:"), foreground=DIM).pack(side="left", padx=2)
        for key, label in (("ground", "Floor in images"), ("transparent", "Transparent background"),
                           ("numbers", "Numbers"), ("names", "Names"), ("descriptions", "Descriptions")):
            checks = images if key in ("ground", "transparent") else captions
            var = tk.BooleanVar()
            ttk.Checkbutton(checks, text=tr(label), variable=var,
                            command=lambda k=key, v=var: self.act("set", [k, v.get()])).pack(side="left", padx=2)
            self.flags[key] = var
        ttk.Label(s, text=tr("Grid (columns × rows)"), foreground=DIM).grid(row=4, column=0, columnspan=4, sticky="w", padx=4)
        self.layout_frame = ttk.Frame(s)
        self.layout_frame.grid(row=5, column=0, columnspan=4, sticky="w", padx=2, pady=(0, 4))
        self.layout_buttons = []

        # Preview bar and pages.
        bar = ttk.Frame(w)
        bar.pack(fill="x", padx=8, pady=(4, 0))
        ttk.Button(bar, text="−", width=3, command=lambda: self.set_zoom(self.zoom / 1.25)).pack(side="left")
        self.zoom_label = ttk.Label(bar, width=6, anchor="center", foreground=DIM)
        self.zoom_label.pack(side="left")
        ttk.Button(bar, text="+", width=3, command=lambda: self.set_zoom(self.zoom * 1.25)).pack(side="left")
        ttk.Button(bar, text="◀", width=3, command=lambda: self.show_page(self.page_shown - 1)).pack(side="left", padx=(10, 0))
        self.page_label = ttk.Label(bar, width=14, anchor="center", foreground=DIM)
        self.page_label.pack(side="left")
        ttk.Button(bar, text="▶", width=3, command=lambda: self.show_page(self.page_shown + 1)).pack(side="left")
        self.undo_button = ttk.Button(bar, text="↶", width=3, command=lambda: self.act("undo"))
        self.redo_button = ttk.Button(bar, text="↷", width=3, command=lambda: self.act("redo"))
        self.redo_button.pack(side="right")
        self.undo_button.pack(side="right")
        frame = ttk.Frame(w)
        frame.pack(fill="both", expand=True, padx=8, pady=4)
        self.canvas = tk.Canvas(frame, bg="#5a606a", highlightthickness=0)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=lambda a, b: (scroll.set(a, b), self._track_page()))
        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        # Redrawn once the size settles: drawing (and making images) inside Windows' resize loop can
        # crash Tk.
        self.canvas.bind("<Configure>", lambda e: self.redraw_later())
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.hint = ttk.Label(w, foreground=DIM, wraplength=600)

        # The selected figure.
        self.entry = ttk.LabelFrame(w, text="")
        self.entry_name = tk.StringVar()
        e = self.entry
        ttk.Label(e, text=tr("Name"), foreground=DIM).grid(row=0, column=0, sticky="w", padx=4)
        name = ttk.Entry(e, textvariable=self.entry_name, width=30)
        name.grid(row=0, column=1, columnspan=3, sticky="we", padx=4, pady=2)
        name.bind("<Return>", lambda ev: self._entry_text())
        name.bind("<FocusOut>", lambda ev: self._entry_text())
        ttk.Label(e, text=tr("Description"), foreground=DIM).grid(row=1, column=0, sticky="nw", padx=4)
        self.description = tk.Text(e, height=2, width=40, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
                                   wrap="word", font=("Segoe UI", 9))
        self.description.grid(row=1, column=1, columnspan=3, sticky="we", padx=4, pady=2)
        self.description.bind("<FocusOut>", lambda ev: self._entry_text())
        ttk.Label(e, text=tr("Goes in as"), foreground=DIM).grid(row=2, column=0, sticky="w", padx=4)
        self.entry_mode = ttk.Combobox(e, state="readonly", width=24)
        self.entry_mode.grid(row=2, column=1, sticky="w", padx=4, pady=2)
        self.entry_mode.bind("<<ComboboxSelected>>", lambda ev: self.act(
            "entry", ["mode", ([None] + list(composer.MODES))[self.entry_mode.current()]]))
        ttk.Label(e, text=tr("Floor"), foreground=DIM).grid(row=2, column=2, sticky="w", padx=4)
        self.entry_ground = ttk.Combobox(e, state="readonly", width=20)
        self.entry_ground.grid(row=2, column=3, sticky="w", padx=4, pady=2)
        self.entry_ground.bind("<<ComboboxSelected>>", lambda ev: self.act(
            "entry", ["ground", (None, True, False)[self.entry_ground.current()]]))
        e.columnconfigure(1, weight=1)
        buttons = ttk.Frame(e)
        buttons.grid(row=3, column=0, columnspan=4, sticky="w", pady=2)
        self.move_buttons = {}
        for key, label, tip, arg in (("up", "↑", "Move earlier", ("step", -1)), ("down", "↓", "Move later", ("step", 1)),
                                     ("prev", "⇞", "Move to the page before", ("page", -1)),
                                     ("next", "⇟", "Move to the page after", ("page", 1))):
            b = ttk.Button(buttons, text=label, width=3, command=lambda a=arg: self.act(*a))
            b.pack(side="left", padx=2)
            self.move_buttons[key] = b
        ttk.Button(buttons, text=tr("Duplicate"), command=lambda: self.act("duplicate")).pack(side="left", padx=2)
        ttk.Button(buttons, text=tr("Delete"), command=lambda: self.act("delete")).pack(side="left", padx=2)
        more = ttk.Frame(e)
        more.grid(row=4, column=0, columnspan=4, sticky="w", pady=(0, 4))
        ttk.Button(more, text=tr("Edit in Stickman"), command=lambda: self.act("edit")).pack(side="left", padx=2)
        ttk.Button(more, text=tr("Replace with the editor's pose"), command=lambda: self.act("replace")).pack(side="left", padx=2)

    def _margin(self):
        try:
            self.act("set", ["margin", float(self.margin_var.get())])
        except ValueError:
            self.refresh()

    def _entry_text(self):
        data = self.host.composer_summary().get("doc")
        if not data or data["selected"] is None:
            return
        e = data["entries"][data["selected"]]
        name, description = self.entry_name.get(), self.description.get("1.0", "end").rstrip("\n")
        if name != e["name"]:
            self.act("entry", ["name", name])
        if description != e["description"]:
            self.act("entry", ["description", description])

    # --- the state ----------------------------------------------------------------------

    def refresh(self):
        if not self.win.winfo_exists():
            return
        data = self.host.composer_summary()
        self.data = data
        self.doc_choice.configure(values=data["docs"])
        if data["current"] is not None:
            self.doc_choice.current(data["current"])
        else:
            self.doc_choice.set("")
        doc = data.get("doc")
        state = "normal" if doc else "disabled"
        for child in self.settings.winfo_children():
            self._set_state(child, state)
        if not doc:
            self.entry.pack_forget()
            self.hint.configure(text=tr("No document yet. Press New, or add a figure with Add to Document (N): a document is made for it."))
            self.hint.pack(fill="x", padx=8, before=self.canvas.master)
            self.canvas.delete("all")
            return
        self.hint.pack_forget()
        s = doc["settings"]
        self.name_var.set(doc["name"])
        self.format_box.current(composer.FORMATS.index(s["format"]))
        self.orient_box.current(0 if s["orientation"] == "portrait" else 1)
        self.mode_box.current(composer.MODES.index(s["mode"]))
        self.margin_var.set(f"{s['margin']:g}")
        for key, var in self.flags.items():
            var.set(s[key])
        self._layouts(s)
        self.undo_button.state(["!disabled"] if doc["can_undo"] else ["disabled"])
        self.redo_button.state(["!disabled"] if doc["can_redo"] else ["disabled"])
        if doc["selected"] is not None and doc["entries"]:
            self._entry_panel(doc)
        else:
            self.entry.pack_forget()
            if not doc["entries"]:
                self.hint.configure(text=tr("Choose an exercise or pose a figure, then press Add to Document (N)."))
                self.hint.pack(fill="x", padx=8, before=self.canvas.master)
        self.draw_pages()

    @staticmethod
    def _set_state(widget, state):
        try:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state="readonly" if state == "normal" else "disabled")
            else:
                widget.configure(state=state)
        except tk.TclError:
            for child in widget.winfo_children():
                ComposerWindow._set_state(child, state)

    def _layouts(self, s):
        key = (s["orientation"], s["columns"], s["rows"])
        if getattr(self, "_layout_key", None) == key:
            return
        self._layout_key = key
        for b in self.layout_buttons:
            b.destroy()
        self.layout_buttons = []
        landscape = s["orientation"] == "landscape"
        for n, (c, r) in enumerate(composer.LAYOUTS):
            active = (c, r) == (s["columns"], s["rows"])
            pw, ph = (30, 21) if landscape else (21, 30)
            icon = tk.Canvas(self.layout_frame, width=38, height=46, bg=ACTIVE if active else PANEL, highlightthickness=0,
                             cursor="hand2")
            x0, y0 = (38 - pw) / 2, 3
            icon.create_rectangle(x0, y0, x0 + pw, y0 + ph, fill="white", outline="")
            cw, ch = (pw - 3) / c, (ph - 3) / r
            for i in range(c):
                for j in range(r):
                    icon.create_rectangle(x0 + 2 + i * cw, y0 + 2 + j * ch, x0 + 1 + (i + 1) * cw, y0 + 1 + (j + 1) * ch,
                                          fill="#788caa", outline="")
            icon.create_text(19, 40, text=f"{c}×{r}", fill=TEXT, font=("Consolas", 8))
            icon.bind("<Button-1>", lambda e, c=c, r=r: self.act("layout", [c, r]))
            icon.grid(row=n // 8, column=n % 8, padx=2, pady=2)
            self.layout_buttons.append(icon)

    def _entry_panel(self, doc):
        i = doc["selected"]
        e = doc["entries"][i]
        self.entry.configure(text=tr("Figure {}").format(i + 1) + " · " + tr("page {}").format(e["page"]))
        if self.win.focus_get() is not self.description:
            self.description.delete("1.0", "end")
            self.description.insert("1.0", e["description"])
        self.entry_name.set(e["name"])
        modes = [tr(composer.MODE_NAMES[m]) for m in composer.MODES]
        s = doc["settings"]
        self.entry_mode.configure(values=[tr("Document's choice ({})").format(tr(composer.MODE_NAMES[s["mode"]]))] + modes)
        self.entry_mode.current(0 if e["mode"] is None else 1 + composer.MODES.index(e["mode"]))
        self.entry_ground.configure(values=[tr("Document's choice ({})").format(tr("on" if s["ground"] else "off")),
                                            tr("on"), tr("off")])
        self.entry_ground.current(0 if e["ground"] is None else 1 if e["ground"] else 2)
        last, cap = len(doc["entries"]) - 1, doc["capacity"]
        enabled = {"up": i > 0, "down": i < last, "prev": i >= cap, "next": i // cap != last // cap}
        for key, b in self.move_buttons.items():
            b.state(["!disabled"] if enabled[key] else ["disabled"])
        self.entry.pack(fill="x", padx=8, pady=(0, 8), after=self.canvas.master)

    # --- the pages -----------------------------------------------------------------------

    _pending = None

    def redraw_later(self, delay=120):
        if self._pending is not None:
            self.win.after_cancel(self._pending)
        self._pending = self.win.after(delay, self._redraw)

    def _redraw(self):
        self._pending = None
        self.draw_pages()

    def set_zoom(self, zoom):
        self.zoom = min(4.0, max(0.3, zoom))
        self.redraw_later(30)

    def _geometry(self):
        doc = self.data["doc"]
        pw, ph = doc["page"]
        avail_w = max(100, self.canvas.winfo_width() - 2 * PAGE_GAP)
        avail_h = max(100, self.canvas.winfo_height() - 2 * PAGE_GAP)
        fit = min(avail_w, avail_h * pw / ph * 1.6)
        scale = min(MAX_PAGE, max(80, fit * self.zoom)) / pw
        left = max(PAGE_GAP, (self.canvas.winfo_width() - pw * scale) / 2)
        return pw, ph, scale, left

    def page_top(self, p):
        pw, ph, scale, _ = self._geometry()
        return PAGE_GAP + p * (ph * scale + PAGE_GAP + 16) + 16

    def draw_pages(self):
        c = self.canvas
        c.delete("all")
        doc = self.data.get("doc") if hasattr(self, "data") else None
        if not doc or not c.winfo_width() > 1:
            return
        self.zoom_label.configure(text=f"{round(self.zoom * 100)}%")
        pw, ph, scale, left = self._geometry()
        mx, my, mw, mh = doc["content"]
        family = ttf.FAMILY if ttf.FAMILY in self._families() else ttf.OFFICE_FONT
        shown = set()
        for p, cells in enumerate(doc["pages"]):
            top = self.page_top(p)
            c.create_text(left + pw * scale / 2, top - 9, text=tr("Page {} of {}").format(p + 1, len(doc["pages"])),
                          fill=TEXT, font=("Consolas", 9))
            c.create_rectangle(left + 3, top + 3, left + pw * scale + 3, top + ph * scale + 3, fill="#3c4048", outline="")
            c.create_rectangle(left, top, left + pw * scale, top + ph * scale, fill="white", outline="")
            c.create_rectangle(left + mx * scale, top + my * scale, left + (mx + mw) * scale, top + (my + mh) * scale,
                               outline="#b4bec8", dash=(3, 3))
            for cell in cells:
                x, y, w, h = cell["figure"]
                cx, cy, cw, ch = cell["cell"]
                X, Y = left + x * scale, top + y * scale
                size = (max(1, round(w * scale)), max(1, round(h * scale)))
                photo = self.photo(cell["key"], size)
                if photo is not None:
                    c.create_image(X, Y, image=photo, anchor="nw")
                    shown.add((cell["key"],) + size)
                if cell["entry"] == doc["selected"]:
                    c.create_rectangle(left + cx * scale - 1, top + cy * scale - 1, left + (cx + cw) * scale + 1,
                                       top + (cy + ch) * scale + 1, outline=ACTIVE, width=2)
                if cell["mode"] != "image":
                    c.create_text(left + cx * scale + 3, top + cy * scale + 3, anchor="nw", fill="white",
                                  text="3D" if cell["mode"] == "model" else "2D", font=("Consolas", 8, "bold"))
                for line in cell["lines"]:
                    px = max(1, round(line["size"] * composer.PT * scale))
                    c.create_text(left + (line["x"] + line["width"] / 2) * scale,
                                  top + (line["top"] + line["height"] / 2) * scale, text=line["text"], fill="#1a1a1a",
                                  font=(family, -px, "bold" if line["bold"] else "normal"))
            line = doc["attribution"]
            c.create_text(left + (line["x"] + line["width"] / 2) * scale, top + (line["top"] + line["height"] / 2) * scale,
                          text=line["text"], fill="#666666",
                          font=(family, -max(1, round(line["size"] * composer.PT * scale))))
        total = self.page_top(len(doc["pages"])) + PAGE_GAP
        c.configure(scrollregion=(0, 0, max(c.winfo_width(), left * 2 + pw * scale), total))
        self.photos = {k: v for k, v in self.photos.items() if k in shown}
        self.host.composer_keep()
        self._track_page()

    def photo(self, key, size):
        """The preview picture of key at size as a Tk image (the host renders it), or None."""
        if (key,) + size not in self.photos:
            import base64
            png = self.host.composer_png(key, size)
            if png is None:
                return None
            self.photos[(key,) + size] = tk.PhotoImage(master=self.win, data=base64.b64encode(png))
        return self.photos[(key,) + size]

    _family_list = None

    def _families(self):
        if ComposerWindow._family_list is None:
            from tkinter import font
            ComposerWindow._family_list = set(font.families(self.win))
        return ComposerWindow._family_list

    def show_page(self, k):
        doc = self.data.get("doc")
        if not doc:
            return
        self.page_shown = max(0, min(len(doc["pages"]) - 1, k))
        total = self.page_top(len(doc["pages"])) + PAGE_GAP
        self.canvas.yview_moveto((self.page_top(self.page_shown) - 18) / total)
        self._track_page()

    def _track_page(self):
        doc = self.data.get("doc") if hasattr(self, "data") else None
        if not doc:
            return
        top = self.canvas.canvasy(0)
        k = 0
        for p in range(len(doc["pages"])):
            if self.page_top(p) + self._geometry()[1] * self._geometry()[2] > top + 40:
                k = p
                break
        self.page_shown = k
        self.page_label.configure(text=tr("Page {} of {}").format(k + 1, len(doc["pages"])))

    def _wheel(self, e):
        if e.state & 0x4:  # Ctrl: zoom
            self.set_zoom(self.zoom * (1.15 if e.delta > 0 else 1 / 1.15))
        else:
            self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

    # --- selecting and dragging --------------------------------------------------------------

    def _slot_at(self, x, y):
        """(entry under the point or None, index of the grid place under it or None)."""
        doc = self.data.get("doc")
        if not doc:
            return None, None
        x, y = self.canvas.canvasx(x), self.canvas.canvasy(y)
        pw, ph, scale, left = self._geometry()
        for p, cells in enumerate(doc["pages"]):
            top = self.page_top(p)
            if not (left <= x <= left + pw * scale and top <= y <= top + ph * scale):
                continue
            mx_, my_ = (x - left) / scale, (y - top) / scale
            hit = next((cell["entry"] for cell in cells
                        if cell["cell"][0] <= mx_ <= cell["cell"][0] + cell["cell"][2]
                        and cell["cell"][1] <= my_ <= cell["cell"][1] + cell["cell"][3]), None)
            mx, my, mw, mh = doc["content"]
            cols, rows = doc["settings"]["columns"], doc["settings"]["rows"]
            col = max(0, min(cols - 1, int((mx_ - mx) // (mw / cols))))
            row = max(0, min(rows - 1, int((my_ - my) // (mh / rows))))
            return hit, min(len(doc["entries"]) - 1, p * doc["capacity"] + row * cols + col)
        return None, None

    def _press(self, e):
        self.canvas.focus_set()
        hit, _ = self._slot_at(e.x, e.y)
        self.drag = {"from": hit, "start": (e.x, e.y), "moving": False}
        if hit is not None and hit != self.data["doc"]["selected"]:
            self.act("select", hit)

    def _motion(self, e):
        d = self.drag
        if not d or d["from"] is None:
            return
        if not d["moving"] and abs(e.x - d["start"][0]) + abs(e.y - d["start"][1]) < 6:
            return
        d["moving"] = True
        self.canvas.delete("ghost")
        x, y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        self.canvas.create_rectangle(x + 6, y + 6, x + 56, y + 66, outline=ACTIVE, width=2, fill="white",
                                     stipple="gray50", tags="ghost")
        self.canvas.configure(cursor="fleur")

    def _release(self, e):
        d, self.drag = self.drag, None
        self.canvas.delete("ghost")
        self.canvas.configure(cursor="")
        if d and d["moving"] and d["from"] is not None:
            _, to = self._slot_at(e.x, e.y)
            if to is not None and to != d["from"]:
                self.act("move", to)
