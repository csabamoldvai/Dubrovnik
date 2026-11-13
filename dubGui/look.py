"""Look of the Workbench: widget styles, the colour palette and the functions that
apply them to CustomTkinter and ttk. Importing this module sets the appearance
mode and installs the palette in the CustomTkinter theme, so import it before
the first window is created."""
import tkinter
from tkinter import ttk
import customtkinter as ctk
from customtkinter.windows.widgets.scaling import CTkScalingBaseClass, ScalingTracker

# Compact radio buttons (CTk defaults are 22 px with a thick ring)
RADIO_STYLE = dict(radiobutton_width=16, radiobutton_height=16,
                   border_width_unchecked=2, border_width_checked=4)

# Checkboxes sized to match the radio buttons above
CHECKBOX_STYLE = dict(checkbox_width=16, checkbox_height=16,
                      border_width=2, corner_radius=3)

PANEL_BORDER = 1

ENTRY_HEIGHT = 24   # entry boxes / combo box height (CTk default is 28)

ctk.set_appearance_mode('System')      # 'System' | 'Light' | 'Dark'
ctk.set_default_color_theme('blue')    # 'blue' | 'dark-blue' | 'green'

# ---------------------------------------------------------------------------
# Colour palette. Every colour is (light mode, dark mode); CustomTkinter picks
# the right one from the appearance mode. Change the look of the whole app here.
# ---------------------------------------------------------------------------
PAL = dict(
    window=('#DDE1E6', '#1E2126'),        # main window background
    panel=('#EEF0F3', '#2A2E35'),         # panels / cards
    panel_border=('#C5CBD3', '#3A3F47'),
    entry=('#FFFFFF', '#1F2329'),         # entry / combo box fill
    entry_border=('#B8BEC7', '#4A515B'),
    text=('#22262B', '#E3E6EA'),
    text_muted=('#5B6470', '#9AA3AE'),
    text_disabled=('#9AA1AB', '#6B727C'),
    accent=('#2F6FB5', '#3B7DC4'),        # buttons, selected radio/check
    accent_hover=('#255A94', '#2F6FB5'),
    control_border=('#6B7480', '#8A929C'),  # radio / checkbox outline
    hover=('#D0D6DE', '#3A4048'),         # menu bar hover, dropdown hover
)

# Terminal colour themes (independent of the light/dark appearance of the window)
TERM_THEMES = {
    'dark': dict(bg='#1B1F24', fg='#D6DBE1', select='#34506E'),
    'light': dict(bg='#FFFFFF', fg='#22262B', select='#B5D5FF'),
}


# CustomTkinter colours the title bar of every dialog by hiding the window and showing it again
# (at creation, and once more 10 ms after each resizable() call): a visible flash and a delay
# on every dialog. Switched off here; newToplevel() sets the title bar colour before the dialog
# is shown instead.
ctk.CTkToplevel._deactivate_windows_window_header_manipulation = True


def titleBarColour(win):
    """Dark or light title bar (Windows 10/11) to match the appearance mode. Works on a window
    that is not shown yet; if the Windows call fails the title bar keeps its default colour."""
    try:
        value = ctypes.c_int(1 if ctk.get_appearance_mode() == 'Dark' else 0)
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        for attribute in (20, 19):          # DWMWA_USE_IMMERSIVE_DARK_MODE, before Windows 10 20H1
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:
        pass


def newToplevel(root):
    """A CTkToplevel for a dialog: hidden until showDialog() or showCentered() is called, so
    the window appears finished and in place, never half built. It also has the display scale
    of the main window from the start.
    Tk puts a new window at the top left of the primary display, and CustomTkinter reads the
    display scale from there. On a main window that sits on a display with another scale,
    it built the dialog at the wrong scale, saw the scale change a moment after the dialog
    moved to the main window, and rebuilt every widget in it (visible flicker). Here the
    dialog starts at the main window's position and takes its scale, so nothing has to
    be recalculated while it is open. A real change later (the dialog or the main window
    moved to another display, or the Windows scale changed) is still found by CustomTkinter."""
    win = ctk.CTkToplevel(root)
    win.withdraw()
    ScalingTracker.window_dpi_scaling_dict[win] = ScalingTracker.window_dpi_scaling_dict[
        ScalingTracker.get_window_root_of_widget(root)]
    # CTkToplevel.geometry() would scale the numbers: ask Tk itself (physical pixels)
    tkinter.Toplevel.geometry(win, f'+{root.winfo_x()}+{root.winfo_y()}')
    dpi = ScalingTracker.window_dpi_scaling_dict[win]
    # the base class method only stores the scale (CTkToplevel's own one also forces a size)
    CTkScalingBaseClass._set_scaling(win, dpi * ScalingTracker.widget_scaling,
                                     dpi * ScalingTracker.window_scaling)
    titleBarColour(win)
    # a dialog dragged to a display with another scale: see fitToContent
    ScalingTracker.add_window(lambda *_scales: win.after(1700, lambda: fitToContent(win)), win)
    return win


def fitToContent(win):
    """After a change of display scale, a dialog of fixed size (resizable(False, False)) takes
    the size its widgets now ask for. When the user drags a dialog to a display with another
    scale, the widgets are rescaled at once but Windows ignores the new window size CustomTkinter
    sets while the mouse button is still down: the window keeps its old size and cuts the
    content off. Called after CustomTkinter has finished (it resets the size limits at 1 s)."""
    try:
        if not win.winfo_exists() or any(tkinter.Toplevel.resizable(win)):
            return                      # gone, or the user can resize it and scroll
        win.update_idletasks()
        tkinter.Toplevel.geometry(win, f'{win.winfo_reqwidth()}x{win.winfo_reqheight()}')
    except tkinter.TclError:
        pass                            # closed meanwhile


def showCentered(win, root, size=None):
    """Centres a dialog made by newToplevel over root and shows it. size: (width, height) in
    unscaled px of a dialog that has a fixed size set with geometry(); without it the size the
    widgets ask for is used."""
    win.update_idletasks()
    if size:
        scale = ScalingTracker.get_window_scaling(win)
        width, height = round(size[0] * scale), round(size[1] * scale)
    else:
        width, height = win.winfo_reqwidth(), win.winfo_reqheight()
    x = root.winfo_x() + (root.winfo_width() - width) // 2
    y = root.winfo_y() + (root.winfo_height() - height) // 2
    win.geometry(f'+{max(x, 0)}+{max(y, 0)}')
    win.deiconify()


def styleCombobox(root):
    """Colours the (standard ttk) COM port combo box to match the current
    light/dark appearance; the CTk widgets follow the appearance themselves."""
    i = 1 if ctk.get_appearance_mode() == 'Dark' else 0
    bg, border, fg = PAL['entry'][i], PAL['entry_border'][i], PAL['text'][i]
    style = ttk.Style(root)
    style.theme_use('clam')            # the default theme ignores these colours
    # arrow button: 18 unscaled px wide (the default is a narrow 14 real pixels)
    arrow = round(14 * ScalingTracker.get_widget_scaling(root))
    style.configure('TCombobox', fieldbackground=bg, background=border,
                    foreground=fg, arrowcolor=fg, bordercolor=border,
                    lightcolor=bg, darkcolor=bg, selectbackground=bg,
                    selectforeground=fg, arrowsize=arrow)
    style.map('TCombobox', fieldbackground=[('readonly', bg)],
              foreground=[('readonly', fg)], selectbackground=[('readonly', bg)],
              selectforeground=[('readonly', fg)])
    root.option_add('*TCombobox*Listbox.background', bg)
    root.option_add('*TCombobox*Listbox.foreground', fg)
    root.option_add('*TCombobox*Listbox.selectBackground', PAL['accent'][i])
    root.option_add('*TCombobox*Listbox.selectForeground', '#FFFFFF')


def scaleCombobox(combo, widgetScale):
    """Gives a ttk combo box (and the list that drops down from it) the font of the CTk
    widgets at the given scale. Tk does not rescale such fonts itself, so this is called
    again when the Windows scale changes (the window moves to another display)."""
    font = ctk.CTkFont().create_scaled_tuple(widgetScale)
    combo.configure(font=font)
    combo.option_add('*TCombobox*Listbox.font', font)
    try:    # the list is made once, the first time the box opens: change it too
        popdown = combo.tk.call('ttk::combobox::PopdownWindow', str(combo))
        combo.tk.call(f'{popdown}.f.l', 'configure', '-font', font)
    except Exception:
        pass


def styleMenus(menus):
    """Colours the pop-up menus to match the current light/dark appearance"""
    i = 1 if ctk.get_appearance_mode() == 'Dark' else 0
    for m in menus:
        m.configure(bg=PAL['panel'][i], fg=PAL['text'][i],
                    activebackground=PAL['accent'][i], activeforeground='#FFFFFF',
                    selectcolor=PAL['text'][i])


def applyPalette():
    """Overrides the colours of the loaded CustomTkinter theme with PAL."""
    th = ctk.ThemeManager.theme
    th['CTk']['fg_color'] = list(PAL['window'])
    th['CTkToplevel']['fg_color'] = list(PAL['panel'])
    th['CTkFrame']['fg_color'] = list(PAL['panel'])
    th['CTkFrame']['border_color'] = list(PAL['panel_border'])
    th['CTkLabel']['text_color'] = list(PAL['text'])
    th['CTkButton'].update(fg_color=list(PAL['accent']),
                           hover_color=list(PAL['accent_hover']),
                           text_color=['#FFFFFF', '#FFFFFF'],
                           text_color_disabled=['#C9D6E6', '#8FA3BC'])
    for k in ('CTkEntry', 'CTkComboBox'):
        th[k].update(fg_color=list(PAL['entry']),
                     border_color=list(PAL['entry_border']),
                     text_color=list(PAL['text']))
    th['CTkComboBox'].update(button_color=list(PAL['entry_border']),
                             button_hover_color=list(PAL['control_border']),
                             text_color_disabled=list(PAL['text_disabled']))
    for k in ('CTkRadioButton', 'CTkCheckBox'):
        th[k].update(fg_color=list(PAL['accent']),
                     hover_color=list(PAL['accent_hover']),
                     border_color=list(PAL['control_border']),
                     text_color=list(PAL['text']),
                     text_color_disabled=list(PAL['text_disabled']))
    th['CTkCheckBox']['checkmark_color'] = ['#FFFFFF', '#FFFFFF']


applyPalette()
