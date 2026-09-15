"""Pure retrieval-ranking tests."""
from services.semantic_search import cosine_similarity, rank_units


def test_cosine_similarity_orders_related_vectors():
    query = [1.0, 0.0]
    candidates = [
        {
            "asset_id": "a",
            "intelligence_id": "i",
            "unit_index": 0,
            "start": 0.0,
            "end": 1.0,
            "text": "strong match",
            "embedding": [1.0, 0.0],
        },
        {
            "asset_id": "a",
            "intelligence_id": "i",
            "unit_index": 1,
            "start": 1.0,
            "end": 2.0,
            "text": "weak match",
            "embedding": [0.2, 0.98],
        },
    ]
    ranked = rank_units(query, candidates, limit=5, min_score=-1.0)
    assert ranked[0]["text"] == "strong match"
    assert ranked[0]["score"] > ranked[1]["score"]
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_rank_units_honors_minimum_score_and_limit():
    candidates = [
        {
            "asset_id": "a",
            "intelligence_id": "i",
            "unit_index": idx,
            "start": float(idx),
            "end": float(idx + 1),
            "text": f"u{idx}",
            "embedding": vector,
        }
        for idx, vector in enumerate(([1.0, 0.0], [0.8, 0.2], [-1.0, 0.0]))
    ]
    ranked = rank_units([1.0, 0.0], candidates, limit=1, min_score=0.5)
    assert len(ranked) == 1
    assert ranked[0]["unit_index"] == 0
