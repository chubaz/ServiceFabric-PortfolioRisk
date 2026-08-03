from pathlib import Path

import pytest

from risk_decisions import DecisionConflict, LocalDecisionStore, admit_proposal

from .test_lifecycle import make_proposal


def test_store_is_restart_safe_and_deterministically_listed(tmp_path):
    root = tmp_path / "decisions"
    store = LocalDecisionStore(root)
    created = store.create(admit_proposal(make_proposal()))
    restarted = LocalDecisionStore(root)
    assert restarted.get(created.proposal.proposal_id) == created
    assert restarted.list() == (created,)


def test_store_rejects_symbolic_link_root(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(DecisionConflict, match="symbolic links"):
        LocalDecisionStore(link).list()


def test_store_rejects_stale_optimistic_revision(tmp_path):
    store = LocalDecisionStore(tmp_path / "decisions")
    created = store.create(admit_proposal(make_proposal()))
    with pytest.raises(DecisionConflict, match="reload"):
        store.replace(created, expected_revision="sha256:" + "0" * 64)
