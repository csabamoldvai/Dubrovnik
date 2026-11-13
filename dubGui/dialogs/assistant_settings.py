"""Help > Assistant Settings...: the credentials of the AI model behind the Assistant."""
from tkinter import DISABLED, END, NORMAL
import customtkinter as ctk
from dubGui.look import newToplevel, showCentered
from dubLibs import assistant_config

# provider key -> (text in the list, the entries it uses)
PROVIDERS = {
    'anthropic': ('Anthropic API key', ('apiKey', 'baseUrl', 'model')),
    'gateway': ('Company gateway (token and URL)', ('apiKey', 'baseUrl', 'model')),
    'bedrock': ('AWS Bedrock (AWS credentials)', ('model',)),
    'vertex': ('Google Vertex AI', ('vertexProject', 'vertexRegion', 'model')),
}
LABELS = {'apiKey': 'API key / token', 'baseUrl': 'Base URL (optional)',
          'model': 'Model (optional)', 'vertexProject': 'Vertex project',
          'vertexRegion': 'Vertex region'}
HINTS = {'apiKey': 'Stored encrypted for your Windows account',
         'baseUrl': 'Only for a gateway or proxy',
         'model': 'Empty = the default model'}


class AssistantSettingsDialog:
    """The window is built when the object is created; win is the window.
    root: the parent window. config: the saved settings (assistant_config.load).
    onSave(config): called with the new settings when the user chooses Save."""

    def __init__(self, root, config, onSave):
        self.root = root
        self.onSave = onSave
        self.entries = {}
        self.win = newToplevel(root)
        self.win.title('Assistant Settings')
        self.win.resizable(False, False)
        self.win.transient(root)
        self.font = font = ctk.CTkFont(size=14)

        ctk.CTkLabel(self.win, text='Provider', font=font, anchor='w'
                     ).grid(row=0, column=0, padx=(24, 12), pady=(20, 6), sticky='w')
        self.provider = ctk.CTkOptionMenu(
            self.win, values=[v[0] for v in PROVIDERS.values()], font=font,
            dropdown_font=font, width=300, command=lambda _name: self.gray())
        self.provider.grid(row=0, column=1, padx=(0, 24), pady=(20, 6), sticky='w')

        for row, key in enumerate(LABELS, start=1):
            ctk.CTkLabel(self.win, text=LABELS[key], font=font, anchor='w'
                         ).grid(row=row, column=0, padx=(24, 12), pady=6, sticky='w')
            entry = ctk.CTkEntry(self.win, width=300, font=font,
                                 show='•' if key == 'apiKey' else '',
                                 placeholder_text=HINTS.get(key, ''))
            entry.grid(row=row, column=1, padx=(0, 24), pady=6, sticky='w')
            self.entries[key] = entry

        ctk.CTkLabel(
            self.win, font=font, justify='left', anchor='w', wraplength=470,
            text_color=('gray30', 'gray70'),
            text='Anything left empty is taken from the environment variables '
                 '(ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, DUB_ASSISTANT_MODEL, ...) if they '
                 'are set. Changes apply to the next question you ask.'
        ).grid(row=len(LABELS) + 1, column=0, columnspan=2, padx=24, pady=(8, 4), sticky='w')

        bar = ctk.CTkFrame(self.win, fg_color='transparent')
        bar.grid(row=len(LABELS) + 2, column=0, columnspan=2, padx=24, pady=(8, 20),
                 sticky='ew')
        bar.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(bar, text='Clear', width=90, font=font, command=self.clear
                      ).grid(row=0, column=0, sticky='w')
        ctk.CTkButton(bar, text='Save', width=90, font=font, command=self.save
                      ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(bar, text='Cancel', width=90, font=font, command=self.win.destroy
                      ).grid(row=0, column=2, padx=(8, 0))
        self.win.bind('<Escape>', lambda _e: self.win.destroy())

        self.show(config)
        self.centerOnRoot()

    def centerOnRoot(self):
        win, root = self.win, self.root
        showCentered(win, root)
        win.after(150, lambda: (win.grab_set(), win.focus_set()))

    def providerKey(self):
        text = self.provider.get()
        return next(k for k, v in PROVIDERS.items() if v[0] == text)

    def show(self, config):
        """Puts the settings into the widgets"""
        key = config.get('provider') or 'anthropic'
        self.provider.set(PROVIDERS[key][0])
        for name, entry in self.entries.items():
            entry.configure(state=NORMAL)
            entry.delete(0, END)
            entry.insert(0, config.get(name, ''))
        self.gray()

    def gray(self):
        """Greys out the entries the chosen provider does not use"""
        used = PROVIDERS[self.providerKey()][1]
        for name, entry in self.entries.items():
            entry.configure(state=NORMAL if name in used else DISABLED)

    def settings(self):
        """The settings in the widgets (unused entries are saved empty)"""
        used = PROVIDERS[self.providerKey()][1]
        config = {'provider': self.providerKey()}
        for name, entry in self.entries.items():
            config[name] = entry.get().strip() if name in used else ''
        return config

    def clear(self):
        """Removes the saved credentials"""
        self.onSave({})
        self.win.destroy()

    def save(self):
        self.onSave(self.settings())
        self.win.destroy()
