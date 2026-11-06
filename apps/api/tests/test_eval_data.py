import json
from collections import Counter
from pathlib import Path


def test_ticket_eval_dataset_baseline():
    path = Path(__file__).resolve().parents[1] / "app" / "eval_data" / "ticket_80.jsonl"
    items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert len(items) == 80
    required = {
        "id",
        "input",
        "expected_category",
        "expected_priority",
        "expected_fields",
        "expected_assignee_department",
    }
    assert all(required <= set(item) for item in items)
    assert len({item["id"] for item in items}) == 80

    categories = Counter(item["expected_category"] for item in items)
    assert set(categories) == {
        "account_permission",
        "network_vpn",
        "software",
        "hardware",
        "email_collaboration",
        "security_incident",
        "other",
    }
    assert min(categories.values()) >= 8
    assert set(item["expected_priority"] for item in items) == {"P1", "P2", "P3", "P4"}
