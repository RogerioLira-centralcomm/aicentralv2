# Compat layer: when this package (aicentralv2.config) is imported, forward
# attributes from the sibling module file aicentralv2/config.py, so we can keep
# a single source of truth in config.py while this folder still exists.

import importlib.util
import pathlib
import sys

# Resolve path to aicentralv2/config.py (module file)
_pkg_dir = pathlib.Path(__file__).resolve().parent.parent  # aicentralv2/
_module_path = _pkg_dir / 'config.py'

_spec = importlib.util.spec_from_file_location('aicentralv2_config_module', str(_module_path))
if _spec and _spec.loader:
	_mod = importlib.util.module_from_spec(_spec)
	sys.modules['aicentralv2_config_module'] = _mod
	_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]

	# Re-export important symbols so `from aicentralv2.config import X` works
	for name in ['Config', 'DevelopmentConfig', 'ProductionConfig', 'TestingConfig', 'config', 'PINECONE_CONFIG']:
		if hasattr(_mod, name):
			globals()[name] = getattr(_mod, name)
else:
	raise ImportError(f'Falha ao carregar módulo de configuração em {_module_path}')

__all__ = ['Config', 'DevelopmentConfig', 'ProductionConfig', 'TestingConfig', 'config', 'PINECONE_CONFIG']
# Torna 'aicentralv2.config' um pacote explícito para permitir submódulos como pinecone_config.
