"""Tests for the recommendation scoring module."""
import pytest

from oo_automator.analysis.recommendations import (
    normalize_values,
    calculate_score,
    find_pareto_optimal,
    generate_recommendations,
)


class TestNormalizeValues:
    """Tests for normalize_values function."""

    def test_normalizes_ascending_values(self):
        """Test normalizing a range of values to 0-1 scale."""
        values = [0, 25, 50, 75, 100]
        result = normalize_values(values)
        assert result == [0.0, 0.25, 0.5, 0.75, 1.0]

    def test_normalizes_arbitrary_range(self):
        """Test normalizing arbitrary range to 0-1."""
        values = [10, 20, 30]
        result = normalize_values(values)
        assert result == [0.0, 0.5, 1.0]

    def test_handles_negative_values(self):
        """Test normalizing values including negatives."""
        values = [-10, 0, 10]
        result = normalize_values(values)
        assert result == [0.0, 0.5, 1.0]

    def test_all_same_values_returns_half(self):
        """Test that identical values all become 0.5."""
        values = [5, 5, 5, 5]
        result = normalize_values(values)
        assert result == [0.5, 0.5, 0.5, 0.5]

    def test_two_values(self):
        """Test normalizing just two values."""
        values = [100, 200]
        result = normalize_values(values)
        assert result == [0.0, 1.0]

    def test_single_value_returns_half(self):
        """Test that a single value returns 0.5."""
        values = [42]
        result = normalize_values(values)
        assert result == [0.5]

    def test_empty_list_returns_empty(self):
        """Test that empty list returns empty list."""
        values = []
        result = normalize_values(values)
        assert result == []

    def test_preserves_order(self):
        """Test that output order matches input order."""
        values = [50, 0, 100, 25]
        result = normalize_values(values)
        # 0 -> 0.0, 25 -> 0.25, 50 -> 0.5, 100 -> 1.0
        assert result == [0.5, 0.0, 1.0, 0.25]


class TestCalculateScore:
    """Tests for calculate_score function."""

    @pytest.fixture
    def sample_results(self):
        """Create sample results for testing."""
        return [
            {
                "id": 1,
                "cagr": 20.0,
                "sharpe": 1.5,
                "win_percentage": 60.0,
                "kelly": 0.15,
                "max_drawdown": 15.0,
            },
            {
                "id": 2,
                "cagr": 30.0,
                "sharpe": 2.0,
                "win_percentage": 70.0,
                "kelly": 0.25,
                "max_drawdown": 25.0,
            },
            {
                "id": 3,
                "cagr": 10.0,
                "sharpe": 1.0,
                "win_percentage": 50.0,
                "kelly": 0.10,
                "max_drawdown": 10.0,
            },
        ]

    def test_returns_score_between_0_and_100(self, sample_results):
        """Test that score is between 0 and 100."""
        for result in sample_results:
            score = calculate_score(result, sample_results, goal="balanced")
            assert 0 <= score <= 100

    def test_balanced_goal_weights(self, sample_results):
        """Test balanced goal applies expected weighting."""
        # Result with best sharpe (2.0) should score well in balanced mode
        # since sharpe has highest weight (0.3)
        result = sample_results[1]  # id=2, best sharpe
        score = calculate_score(result, sample_results, goal="balanced")
        # This should have a high score due to good sharpe
        assert score > 50

    def test_maximize_returns_goal_weights(self, sample_results):
        """Test maximize_returns goal favors high CAGR."""
        # Result with best cagr (30.0) should score highest
        high_cagr_result = sample_results[1]  # id=2, cagr=30
        low_cagr_result = sample_results[2]  # id=3, cagr=10

        high_score = calculate_score(high_cagr_result, sample_results, goal="maximize_returns")
        low_score = calculate_score(low_cagr_result, sample_results, goal="maximize_returns")

        assert high_score > low_score

    def test_protect_capital_goal_weights(self):
        """Test protect_capital goal favors low drawdown when other metrics are similar."""
        # Create results where metrics are similar except drawdown
        results = [
            {
                "id": 1,
                "cagr": 20.0,
                "sharpe": 1.5,
                "win_percentage": 60.0,
                "kelly": 0.15,
                "max_drawdown": 10.0,  # Low drawdown - should score higher
            },
            {
                "id": 2,
                "cagr": 20.0,
                "sharpe": 1.5,
                "win_percentage": 60.0,
                "kelly": 0.15,
                "max_drawdown": 30.0,  # High drawdown - should score lower
            },
        ]

        low_dd_score = calculate_score(results[0], results, goal="protect_capital")
        high_dd_score = calculate_score(results[1], results, goal="protect_capital")

        # With protect_capital weights, lower drawdown should score higher
        assert low_dd_score > high_dd_score

    def test_default_goal_is_balanced(self, sample_results):
        """Test that default goal is balanced."""
        result = sample_results[0]
        score_default = calculate_score(result, sample_results)
        score_balanced = calculate_score(result, sample_results, goal="balanced")
        assert score_default == score_balanced

    def test_single_result_gets_middle_score(self):
        """Test that a single result gets approximately 50 (all normalized to 0.5)."""
        results = [
            {
                "id": 1,
                "cagr": 15.0,
                "sharpe": 1.2,
                "win_percentage": 55.0,
                "kelly": 0.12,
                "max_drawdown": 12.0,
            }
        ]
        score = calculate_score(results[0], results, goal="balanced")
        # All values normalize to 0.5, so weighted sum should be 50
        assert score == 50.0

    def test_best_in_all_metrics_scores_100(self):
        """Test that result best in all metrics scores 100."""
        results = [
            {
                "id": 1,
                "cagr": 100.0,
                "sharpe": 3.0,
                "win_percentage": 90.0,
                "kelly": 0.5,
                "max_drawdown": 5.0,  # Lower is better
            },
            {
                "id": 2,
                "cagr": 10.0,
                "sharpe": 0.5,
                "win_percentage": 40.0,
                "kelly": 0.05,
                "max_drawdown": 50.0,
            },
        ]
        score = calculate_score(results[0], results, goal="balanced")
        assert score == 100.0

    def test_worst_in_all_metrics_scores_0(self):
        """Test that result worst in all metrics scores 0."""
        results = [
            {
                "id": 1,
                "cagr": 100.0,
                "sharpe": 3.0,
                "win_percentage": 90.0,
                "kelly": 0.5,
                "max_drawdown": 5.0,
            },
            {
                "id": 2,
                "cagr": 10.0,
                "sharpe": 0.5,
                "win_percentage": 40.0,
                "kelly": 0.05,
                "max_drawdown": 50.0,  # Higher is worse
            },
        ]
        score = calculate_score(results[1], results, goal="balanced")
        assert score == 0.0


class TestFindParetoOptimal:
    """Tests for find_pareto_optimal function."""

    def test_single_result_is_pareto_optimal(self):
        """Test that a single result is always Pareto optimal."""
        results = [{"id": 1, "cagr": 20.0, "sharpe": 1.5, "max_drawdown": 15.0}]
        optimal = find_pareto_optimal(
            results,
            maximize=["cagr", "sharpe"],
            minimize=["max_drawdown"],
        )
        assert len(optimal) == 1
        assert optimal[0]["id"] == 1

    def test_dominated_result_excluded(self):
        """Test that dominated results are excluded from Pareto front."""
        results = [
            # Result 1: Best in all metrics
            {"id": 1, "cagr": 30.0, "sharpe": 2.0, "max_drawdown": 10.0},
            # Result 2: Worse in ALL metrics - dominated
            {"id": 2, "cagr": 20.0, "sharpe": 1.5, "max_drawdown": 20.0},
        ]
        optimal = find_pareto_optimal(
            results,
            maximize=["cagr", "sharpe"],
            minimize=["max_drawdown"],
        )
        assert len(optimal) == 1
        assert optimal[0]["id"] == 1

    def test_tradeoff_results_both_optimal(self):
        """Test that results with tradeoffs are both Pareto optimal."""
        results = [
            # Result 1: Higher CAGR but higher drawdown
            {"id": 1, "cagr": 30.0, "sharpe": 1.5, "max_drawdown": 20.0},
            # Result 2: Lower CAGR but lower drawdown - tradeoff
            {"id": 2, "cagr": 20.0, "sharpe": 1.5, "max_drawdown": 10.0},
        ]
        optimal = find_pareto_optimal(
            results,
            maximize=["cagr", "sharpe"],
            minimize=["max_drawdown"],
        )
        # Both should be optimal as neither dominates the other
        assert len(optimal) == 2
        optimal_ids = {r["id"] for r in optimal}
        assert optimal_ids == {1, 2}

    def test_multiple_dominated_results(self):
        """Test with multiple dominated results."""
        results = [
            # Best overall
            {"id": 1, "cagr": 40.0, "sharpe": 2.5, "max_drawdown": 5.0},
            # Dominated by id=1
            {"id": 2, "cagr": 30.0, "sharpe": 2.0, "max_drawdown": 10.0},
            # Also dominated by id=1
            {"id": 3, "cagr": 20.0, "sharpe": 1.5, "max_drawdown": 15.0},
        ]
        optimal = find_pareto_optimal(
            results,
            maximize=["cagr", "sharpe"],
            minimize=["max_drawdown"],
        )
        assert len(optimal) == 1
        assert optimal[0]["id"] == 1

    def test_pareto_front_with_multiple_optimal(self):
        """Test finding full Pareto front with multiple optimal results."""
        results = [
            # High return, high risk
            {"id": 1, "cagr": 50.0, "sharpe": 1.0, "max_drawdown": 40.0},
            # Medium return, medium risk
            {"id": 2, "cagr": 30.0, "sharpe": 2.0, "max_drawdown": 20.0},
            # Low return, low risk
            {"id": 3, "cagr": 15.0, "sharpe": 2.5, "max_drawdown": 8.0},
            # Dominated by id=2
            {"id": 4, "cagr": 25.0, "sharpe": 1.5, "max_drawdown": 25.0},
        ]
        optimal = find_pareto_optimal(
            results,
            maximize=["cagr", "sharpe"],
            minimize=["max_drawdown"],
        )
        # 1, 2, 3 are on Pareto front; 4 is dominated by 2
        assert len(optimal) == 3
        optimal_ids = {r["id"] for r in optimal}
        assert optimal_ids == {1, 2, 3}

    def test_empty_results_returns_empty(self):
        """Test that empty input returns empty output."""
        optimal = find_pareto_optimal(
            [],
            maximize=["cagr"],
            minimize=["max_drawdown"],
        )
        assert optimal == []

    def test_all_equal_all_optimal(self):
        """Test that when all results are equal, all are optimal."""
        results = [
            {"id": 1, "cagr": 20.0, "sharpe": 1.5, "max_drawdown": 15.0},
            {"id": 2, "cagr": 20.0, "sharpe": 1.5, "max_drawdown": 15.0},
            {"id": 3, "cagr": 20.0, "sharpe": 1.5, "max_drawdown": 15.0},
        ]
        optimal = find_pareto_optimal(
            results,
            maximize=["cagr", "sharpe"],
            minimize=["max_drawdown"],
        )
        assert len(optimal) == 3


class TestGenerateRecommendations:
    """Tests for generate_recommendations function."""

    @pytest.fixture
    def sample_results(self):
        """Create sample results for comprehensive recommendation testing."""
        return [
            {
                "id": 1,
                "cagr": 25.0,
                "sharpe": 2.0,
                "win_percentage": 65.0,
                "kelly": 0.20,
                "max_drawdown": 12.0,
            },
            {
                "id": 2,
                "cagr": 35.0,
                "sharpe": 1.8,
                "win_percentage": 60.0,
                "kelly": 0.18,
                "max_drawdown": 20.0,
            },
            {
                "id": 3,
                "cagr": 15.0,
                "sharpe": 2.2,
                "win_percentage": 70.0,
                "kelly": 0.22,
                "max_drawdown": 8.0,
            },
            {
                "id": 4,
                "cagr": 10.0,
                "sharpe": 0.8,
                "win_percentage": 45.0,
                "kelly": 0.05,
                "max_drawdown": 30.0,
            },
            {
                "id": 5,
                "cagr": 8.0,
                "sharpe": 0.5,
                "win_percentage": 40.0,
                "kelly": 0.03,
                "max_drawdown": 35.0,
            },
        ]

    def test_returns_expected_structure(self, sample_results):
        """Test that output has expected keys."""
        recommendations = generate_recommendations(sample_results, goal="balanced")
        assert "top_pick" in recommendations
        assert "alternatives" in recommendations
        assert "avoid" in recommendations
        assert "goal" in recommendations

    def test_top_pick_is_highest_scored(self, sample_results):
        """Test that top_pick has highest score."""
        recommendations = generate_recommendations(sample_results, goal="balanced")
        top_pick = recommendations["top_pick"]

        # Calculate scores for all
        scores = [calculate_score(r, sample_results, goal="balanced") for r in sample_results]
        max_score = max(scores)

        # Top pick should have the max score
        top_pick_score = calculate_score(top_pick, sample_results, goal="balanced")
        assert top_pick_score == max_score

    def test_alternatives_are_pareto_optimal(self, sample_results):
        """Test that alternatives are from Pareto front."""
        recommendations = generate_recommendations(sample_results, goal="balanced")
        alternatives = recommendations["alternatives"]

        # All alternatives should be Pareto optimal
        pareto = find_pareto_optimal(
            sample_results,
            maximize=["cagr", "sharpe", "win_percentage", "kelly"],
            minimize=["max_drawdown"],
        )
        pareto_ids = {r["id"] for r in pareto}

        for alt in alternatives:
            assert alt["id"] in pareto_ids

    def test_alternatives_limit_to_5(self):
        """Test that alternatives are limited to 5."""
        # Create many results with tradeoffs so many are Pareto optimal
        results = [
            {
                "id": i,
                "cagr": 10 + i * 2,
                "sharpe": 2.5 - i * 0.1,
                "win_percentage": 70 - i * 2,
                "kelly": 0.3 - i * 0.02,
                "max_drawdown": 5 + i * 3,
            }
            for i in range(10)
        ]
        recommendations = generate_recommendations(results, goal="balanced")
        # Should have at most 5 alternatives
        assert len(recommendations["alternatives"]) <= 5

    def test_avoid_contains_low_scoring_dominated(self, sample_results):
        """Test that avoid list contains low-scoring dominated results."""
        recommendations = generate_recommendations(sample_results, goal="balanced")
        avoid = recommendations["avoid"]

        # Avoid should contain dominated results with low scores
        # id=4 and id=5 should be in avoid (low scores, dominated)
        avoid_ids = {r["id"] for r in avoid}
        # At least one of the worst performers should be in avoid
        assert 4 in avoid_ids or 5 in avoid_ids

    def test_avoid_limit_to_3(self):
        """Test that avoid list is limited to 3."""
        # Create many low-scoring results
        results = [
            {
                "id": i,
                "cagr": 50 - i * 5,
                "sharpe": 2.5 - i * 0.2,
                "win_percentage": 80 - i * 5,
                "kelly": 0.3 - i * 0.03,
                "max_drawdown": 5 + i * 5,
            }
            for i in range(10)
        ]
        recommendations = generate_recommendations(results, goal="balanced")
        assert len(recommendations["avoid"]) <= 3

    def test_goal_is_included_in_output(self, sample_results):
        """Test that goal is included in output."""
        for goal in ["balanced", "maximize_returns", "protect_capital"]:
            recommendations = generate_recommendations(sample_results, goal=goal)
            assert recommendations["goal"] == goal

    def test_default_goal_is_balanced(self, sample_results):
        """Test that default goal is balanced."""
        recommendations = generate_recommendations(sample_results)
        assert recommendations["goal"] == "balanced"

    def test_single_result(self):
        """Test with single result."""
        results = [
            {
                "id": 1,
                "cagr": 20.0,
                "sharpe": 1.5,
                "win_percentage": 60.0,
                "kelly": 0.15,
                "max_drawdown": 15.0,
            }
        ]
        recommendations = generate_recommendations(results, goal="balanced")
        assert recommendations["top_pick"]["id"] == 1
        assert recommendations["alternatives"] == []
        assert recommendations["avoid"] == []

    def test_empty_results(self):
        """Test with empty results list."""
        recommendations = generate_recommendations([], goal="balanced")
        assert recommendations["top_pick"] is None
        assert recommendations["alternatives"] == []
        assert recommendations["avoid"] == []
        assert recommendations["goal"] == "balanced"

    def test_top_pick_excluded_from_alternatives(self, sample_results):
        """Test that top pick is not in alternatives."""
        recommendations = generate_recommendations(sample_results, goal="balanced")
        top_pick_id = recommendations["top_pick"]["id"]
        alternative_ids = {r["id"] for r in recommendations["alternatives"]}
        assert top_pick_id not in alternative_ids
