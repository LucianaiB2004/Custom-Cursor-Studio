import importlib.util
from pathlib import Path


def test_preparation_preserves_high_resolution_manifest_and_project(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[2]
    spec=importlib.util.spec_from_file_location('prepare_test',root/'editor/scripts/prepare_root_themes.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'ROOT',tmp_path)
    monkeypatch.setattr(module,'EDITOR_ROOT',tmp_path/'editor')
    monkeypatch.setattr(module,'NAMES',['示例'])
    folder=tmp_path/'示例';(folder/'project').mkdir(parents=True)
    manifest=b'{"variants":{"128":{"roles":{"Arrow":"high-res/Arrow.cur"}}},"default_size":128}'
    (folder/'theme-map.json').write_bytes(manifest)
    (folder/'project/theme.json').write_bytes(b'{"keep":"master"}')
    (folder/'恢复原方案.cmd').write_bytes(b'old-generated-shortcut')
    (tmp_path/'editor/evidence').mkdir(parents=True)
    for name in ['original-sha256.json','reference-locations.json']:
        (tmp_path/'editor/evidence'/name).write_text('{}','utf-8')
    module.main()
    assert (folder/'theme-map.json').read_bytes()==manifest
    assert (folder/'project/theme.json').read_bytes()==b'{"keep":"master"}'
    assert (folder/'编辑主题.cmd').exists() and (folder/'放大与导出.cmd').exists()
    assert not (folder/'恢复原方案.cmd').exists()
    assert b'-ResetDefaults' in (tmp_path/'取消自定义光标.cmd').read_bytes()
