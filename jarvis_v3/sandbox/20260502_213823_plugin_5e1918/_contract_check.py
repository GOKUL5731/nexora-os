import importlib.util, pathlib
path = pathlib.Path(r'C:\Users\gokul\Downloads\jarvis_v3_complete\jarvis_v3\sandbox\20260502_213823_plugin_5e1918\sandbox_test_plugin.py')
spec = importlib.util.spec_from_file_location('candidate_plugin', path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
assert hasattr(mod, 'register'), 'missing register()'
registration = mod.register({})
assert isinstance(registration, dict), 'register() must return dict'
tools = registration.get('tools')
assert isinstance(tools, dict) and tools, 'plugin must expose at least one tool'
for tool_name, handler in tools.items():
    assert callable(handler), f'tool {tool_name} is not callable'
print('PLUGIN_CONTRACT_OK')
