import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.scoring import compute_overall_score, score_to_label, risk_score_to_label


def test_empty_list_returns_none():
    assert compute_overall_score([]) is None


def test_all_failed_returns_none():
    clauses = [{"risk_score": 8, "analysis_failed": True}, {"risk_score": None, "analysis_failed": True}]
    assert compute_overall_score(clauses) is None


def test_failed_clauses_excluded_not_zeroed():
    # If failed clauses were scored as 0, this average would be much lower.
    clauses = [
        {"risk_score": 8, "analysis_failed": False},
        {"risk_score": 8, "analysis_failed": False},
        {"risk_score": None, "analysis_failed": True},
    ]
    assert compute_overall_score(clauses) == 8.0


def test_critical_clause_weighted_double():
    clauses = [
        {"risk_score": 2, "analysis_failed": False},
        {"risk_score": 9, "analysis_failed": False},  # weight 2.0
    ]
    # weighted avg = (2*1 + 9*2) / (1+2) = 20/3 = 6.67
    assert compute_overall_score(clauses) == round(20 / 3, 2)


def test_score_to_label_boundaries():
    assert score_to_label(1.0) == "low"
    assert score_to_label(3.4) == "low"
    assert score_to_label(3.5) == "medium"
    assert score_to_label(5.9) == "medium"
    assert score_to_label(6.0) == "high"
    assert score_to_label(7.9) == "high"
    assert score_to_label(8.0) == "critical"
    assert score_to_label(10.0) == "critical"
    assert score_to_label(None) is None


def test_risk_score_to_label_matches_overall_thresholds():
    assert risk_score_to_label(1) == "low"
    assert risk_score_to_label(9) == "critical"
    assert risk_score_to_label(6) == "high"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
