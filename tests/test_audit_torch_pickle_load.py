from scripts.audit_torch_pickle_load import audit_source

def test_torch_load_allows_weights_only():
    assert audit_source("torch.load(path, weights_only=True)\n") == []

def test_torch_load_reports_pickle_opt_in():
    assert audit_source("torch.load(path, weights_only=False)\n") == ["torch.load disables weights-only loading on line 1"]
