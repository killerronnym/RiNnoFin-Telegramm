"""
invite_bot.py - Recovered from pyc bytecode cache after source deletion.
Loads the full implementation from the compiled bytecode directly.
"""
import importlib.util as _util
import sys as _sys

_PYC_PATH = r'C:\Users\Ronny M PC\Desktop\Telegramm-BotEngelbertStrauss-Gruppe-V1.9.50-2.9.21\bots\invite_bot\__pycache__\invite_bot.cpython-39.pyc'

# Guard against recursive imports
if '_invite_bot_loaded' not in _sys.modules:
    _sys.modules['_invite_bot_loaded'] = True
    _spec = _util.spec_from_file_location('_invite_bot_pyc', _PYC_PATH)
    _impl = _util.module_from_spec(_spec)
    _sys.modules['_invite_bot_pyc'] = _impl
    _spec.loader.exec_module(_impl)
    globals().update({k: v for k, v in vars(_impl).items() if not k.startswith('__')})
else:
    from _invite_bot_pyc import *
    try:
        from _invite_bot_pyc import get_handlers, get_fallback_handlers, setup_jobs, letsgo, generate_profile_text
    except ImportError:
        pass
