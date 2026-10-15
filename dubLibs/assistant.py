"""AI assistant for the Dubrovnik Workbench (Help > Assistant).

The assistant answers questions from the built-in help and writes Python
scripts for the ``dub`` object (see run_py_script.py). It never touches the
board itself: a script it writes is only shown to the user, who decides whether
to run it. This module has no GUI code, so it can be tested on its own.

It is set up in Help > Assistant Settings (see assistant_config.py) or with
environment variables, which fill in whatever the dialog leaves empty (see resolve()):

    ANTHROPIC_API_KEY                 Anthropic API key, or
    ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL   a company gateway, or
    DUB_ASSISTANT_PROVIDER=bedrock | vertex     AWS / Google cloud credentials
                                      (vertex also needs ANTHROPIC_VERTEX_PROJECT_ID)

DUB_ASSISTANT_MODEL overrides the model (cloud providers use their own IDs).
Needs the ``anthropic`` package (``anthropic[bedrock]`` or ``anthropic[vertex]``
for the cloud providers).
"""
import html
import os
import re

from dubLibs import run_py_script, tools

DEFAULT_MODEL = 'claude-sonnet-5-5'
MAX_TOKENS = 4096
MAX_TOOL_ROUNDS = 5
MAX_HISTORY = 40          # messages kept; older ones are dropped

INSTRUCTIONS = """\
You are the assistant built into Dubrovnik Workbench, a PC application for the \
Dubrovnik SPI flash test board and its Tiberias firmware. You help the user \
understand the board and write test scripts.

Rules:
- Answer from the user guide below. If it does not cover something, say so \
rather than guessing command syntax or electrical limits.
- To write a script, call propose_script. The user reviews it and chooses \
whether to run it; you cannot run anything yourself.
- Scripts use only the `dub` object and the standard library. Prefer \
dub.confirm() before anything that erases or reprograms, keep voltages and \
frequencies inside the limits the user states, and write result files with \
dub.output_path().
- Never raise the supply voltage or clock beyond what the user or the guide \
allows. Ask when the device limits are unknown.
- Be brief. The user is a test engineer at the bench.
"""

PROPOSE_TOOL = {
    'name': 'propose_script',
    'description': ('Show the user a Python script for the Workbench to review. '
                    'The user decides whether to run or save it.'),
    'input_schema': {
        'type': 'object',
        'properties': {
            'title': {'type': 'string', 'description': 'Short name of the script'},
            'summary': {'type': 'string',
                        'description': 'What it does, and what it changes on the '
                                       'board (erase, program, voltage, clock)'},
            'code': {'type': 'string', 'description': 'The complete Python source'},
            'destructive': {'type': 'boolean',
                            'description': 'True if it erases or programs flash '
                                           'or changes voltage or clock'},
        },
        'required': ['title', 'summary', 'code', 'destructive'],
    },
}

READ_TOOL = {
    'name': 'read_tool_source',
    'description': ('Return the source of an existing script from the Tools '
                    'menu, as an example to follow or modify.'),
    'input_schema': {
        'type': 'object',
        'properties': {'name': {'type': 'string',
                                'description': 'Name as shown in the Tools menu'}},
        'required': ['name'],
    },
}


def helpText(path):
    """The user guide as plain text (the HTML help file with tags removed)"""
    try:
        with open(path, encoding='utf-8') as fh:
            raw = fh.read()
    except OSError:
        return ''
    raw = re.sub(r'(?is)<(script|style).*?</\1>', '', raw)
    raw = re.sub(r'(?i)</(p|div|li|tr|h\d|pre)>|<br\s*/?>', '\n', raw)
    text = html.unescape(re.sub(r'<[^>]+>', '', raw))
    return re.sub(r'\n\s*\n+', '\n\n', text).strip()


def resolve(saved=None):
    """The settings to use: what was saved in the dialog (a dict as made by
    assistant_config.load), and for every field left empty there the environment
    variable. Returns a dict with provider ('anthropic', 'gateway', 'bedrock',
    'vertex' or '' if nothing is set), apiKey, baseUrl, model, vertexProject,
    vertexRegion."""
    saved, env = saved or {}, os.environ
    provider = saved.get('provider') or env.get('DUB_ASSISTANT_PROVIDER', '').lower()
    if provider not in ('anthropic', 'gateway', 'bedrock', 'vertex'):
        if env.get('ANTHROPIC_AUTH_TOKEN') and env.get('ANTHROPIC_BASE_URL'):
            provider = 'gateway'
        elif env.get('ANTHROPIC_API_KEY') or env.get('DUB_ASSISTANT_PROVIDER'):
            provider = 'anthropic'
        else:
            provider = ''
    keyVar = 'ANTHROPIC_AUTH_TOKEN' if provider == 'gateway' else 'ANTHROPIC_API_KEY'
    return dict(
        provider=provider,
        apiKey=saved.get('apiKey') or env.get(keyVar, ''),
        baseUrl=saved.get('baseUrl') or env.get('ANTHROPIC_BASE_URL', ''),
        model=saved.get('model') or env.get('DUB_ASSISTANT_MODEL', '') or DEFAULT_MODEL,
        vertexProject=saved.get('vertexProject') or env.get('ANTHROPIC_VERTEX_PROJECT_ID', ''),
        vertexRegion=saved.get('vertexRegion') or env.get('CLOUD_ML_REGION', '') or 'global')


def configured(saved=None):
    """True if the saved settings or the environment name a way to reach a model"""
    c = resolve(saved)
    if c['provider'] == 'anthropic':
        return bool(c['apiKey'])
    if c['provider'] == 'gateway':
        return bool(c['apiKey'] and c['baseUrl'])
    return c['provider'] in ('bedrock', 'vertex')


def _isToolResult(message):
    content = message['content']
    return isinstance(content, list) and any(
        isinstance(b, dict) and b.get('type') == 'tool_result' for b in content)


class Assistant:
    def __init__(self, helpPath, toolsFolder, config=None):
        """config: the saved settings (assistant_config.load), see resolve()"""
        self.toolsFolder = toolsFolder
        self.saved = config
        self.model = resolve(config)['model']
        self.messages = []
        self.pendingNotes = []        # what happened to earlier proposals
        self.client = None
        names = ', '.join(t['name'] for t in tools.find_tools(toolsFolder))
        self.system = [
            {'type': 'text', 'text': INSTRUCTIONS},
            {'type': 'text',
             'text': ('# The dub object (dubLibs/run_py_script.py)\n'
                      + (run_py_script.__doc__ or '')
                      + '\nExisting tools: ' + (names or 'none')
                      + '\n\n# User guide\n' + helpText(helpPath)),
             'cache_control': {'type': 'ephemeral'}},   # large, reused every turn
        ]

    def configure(self, config):
        """Uses new settings from now on (the next question makes a new client)"""
        self.saved = config
        self.model = resolve(config)['model']
        self.client = None

    def available(self):
        """Returns '' if the assistant can run, else the reason it can't"""
        try:
            import anthropic   # noqa: F401
        except ImportError:
            return ('The assistant needs the "anthropic" package:\n'
                    'pip install anthropic')
        if not configured(self.saved):
            return ('The assistant is not set up yet.\n\n'
                    'Enter your credentials in Help > Assistant Settings.')
        return ''

    def makeClient(self):
        import anthropic
        c = resolve(self.saved)
        if c['provider'] == 'bedrock':
            return anthropic.AnthropicBedrock()         # AWS credentials as usual
        if c['provider'] == 'vertex':
            return anthropic.AnthropicVertex(project_id=c['vertexProject'] or None,
                                             region=c['vertexRegion'])
        if c['provider'] == 'gateway':
            return anthropic.Anthropic(auth_token=c['apiKey'], base_url=c['baseUrl'])
        return anthropic.Anthropic(api_key=c['apiKey'], base_url=c['baseUrl'] or None)

    def note(self, text):
        """Records an event (script run, stopped, saved) for the next turn"""
        self.pendingNotes.append(text)

    def reset(self):
        self.messages, self.pendingNotes = [], []

    def toolSource(self, name):
        for tool in tools.find_tools(self.toolsFolder):
            if tool['name'].lower() == name.strip().lower():
                with open(tool['path'], encoding='utf-8-sig') as fh:
                    return fh.read()
        return f'No tool named "{name}".'

    def ask(self, text, onText, onScript):
        """Sends the user's message and runs the tool loop. Blocking: call it
        from a worker thread. onText(str) gets the assistant's text and
        onScript(dict) a proposed script. Raises on API errors."""
        if self.client is None:
            self.client = self.makeClient()
        if self.pendingNotes:
            text = ('[Workbench events since your last message: '
                    + '; '.join(self.pendingNotes) + ']\n\n' + text)
            self.pendingNotes = []
        self.messages.append({'role': 'user', 'content': text})
        self.messages = self.messages[-MAX_HISTORY:]
        while self.messages and (self.messages[0]['role'] != 'user'
                                 or _isToolResult(self.messages[0])):
            self.messages.pop(0)      # history must start with a user text turn
        for _ in range(MAX_TOOL_ROUNDS):
            reply = self.client.messages.create(
                model=self.model, max_tokens=MAX_TOKENS, system=self.system,
                tools=[PROPOSE_TOOL, READ_TOOL], messages=self.messages)
            self.messages.append({'role': 'assistant', 'content': reply.content})
            results = []
            for block in reply.content:
                if block.type == 'text' and block.text.strip():
                    onText(block.text)
                elif block.type == 'tool_use':
                    if block.name == 'propose_script':
                        onScript(dict(block.input))
                        out = ('Shown to the user, who decides whether to run '
                               'it. Do not repeat the code in your reply.')
                    elif block.name == 'read_tool_source':
                        out = self.toolSource(block.input.get('name', ''))
                    else:
                        out = 'Unknown tool.'
                    results.append({'type': 'tool_result',
                                    'tool_use_id': block.id, 'content': out})
            if not results:
                return
            self.messages.append({'role': 'user', 'content': results})
        onText('(stopped: too many tool steps)')
