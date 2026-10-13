"""Look of the Workbench: widget styles, the colour palette and the functions that
apply them to CustomTkinter and ttk. Importing this module sets the appearance
mode and installs the palette in the CustomTkinter theme, so import it before
the first window is created."""
from tkinter import ttk
import customtkinter as ctk
from customtkinter.windows.widgets.scaling import ScalingTracker

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
