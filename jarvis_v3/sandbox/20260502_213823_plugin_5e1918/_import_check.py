import importlib.util, pathlib
path = pathlib.Path(r'C:\Users\gokul\Downloads\jarvis_v3_complete\jarvis_v3\sandbox\20260502_213823_plugin_5e1918\sandbox_test_plugin.py')
spec = importlib.util.spec_from_file_location('candidate_module', path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print('IMPORT_OK')
