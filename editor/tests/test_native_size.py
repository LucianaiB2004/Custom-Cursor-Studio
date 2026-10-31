import pytest
from cursor_studio.windows import schemes
from test_schemes import Registry, files

def test_apply_size_is_written_transactionally_and_restored(tmp_path,monkeypatch):
    registry=Registry()
    registry.state['cursors']['values']['CursorBaseSize']={'type':4,'data':32}
    before=registry.snapshot()
    monkeypatch.setattr(schemes,'_backend',lambda:registry)
    monkeypatch.setattr(schemes,'_validate_file',lambda _:True)
    backup=schemes.apply_files(files(tmp_path),'大号',tmp_path/'backups',size=96)
    assert registry.state['cursors']['values']['CursorBaseSize']=={'type':4,'data':96}
    schemes.restore_backup(backup)
    assert registry.state==before

@pytest.mark.parametrize('size',[True,0,300,96.5,'96'])
def test_invalid_size_rejected_before_mutation(tmp_path,monkeypatch,size):
    registry=Registry()
    monkeypatch.setattr(schemes,'_backend',lambda:registry)
    monkeypatch.setattr(schemes,'_validate_file',lambda _:True)
    with pytest.raises(ValueError):schemes.apply_files(files(tmp_path),'大号',tmp_path/'backups',size=size)
    assert registry.refreshes==0
    assert not (tmp_path/'backups').exists()
