"""Offline checks for actual policy changes, feedback attribution, and bounded trials."""
import importlib

import pytest

app = importlib.import_module("patterns.09-learning-and-adaptation.app")


def rate(policy, context, rating):
    answer = app.respond("Support issue", context, policy)
    return policy.feedback(answer.episode_id, rating)


def test_feedback_changes_next_strategy_and_response_structure():
    policy = app.AdaptivePolicy()
    first = app.respond("Upload fails", "technical", policy)
    assert first.selected_strategy == "brief" and "\n" not in first.response
    rejected = policy.feedback(first.episode_id, "not_helpful")
    assert rejected.scores_before == {"brief": 0.5, "guided": 0.5}
    assert rejected.scores_after == {"brief": 0.25, "guided": 0.5}
    second = app.respond("Upload fails", "technical", policy)
    assert second.selected_strategy == "guided" and second.response.count("\n- ") == 2
    accepted = policy.feedback(second.episode_id, "helpful")
    assert accepted.scores_after == {"brief": 0.25, "guided": 0.75}
    assert app.respond("Follow up", "technical", policy).selected_strategy == "guided"


def test_unrated_alternative_is_tried_even_after_positive_first_rating():
    policy = app.AdaptivePolicy()
    rate(policy, "billing", "helpful")
    assert policy.select("billing")[0] == "guided"
    rate(policy, "billing", "not_helpful")
    assert policy.select("billing")[0] == "brief"


def test_without_feedback_scores_do_not_change():
    policy = app.AdaptivePolicy()
    first = app.respond("Issue", "technical", policy)
    second = app.respond("Issue", "technical", policy)
    assert first.selected_strategy == second.selected_strategy == "brief"
    assert policy.scores("technical") == {"brief": 0.5, "guided": 0.5}
    assert all(stats.feedback_count == 0 for stats in policy.statistics("technical").values())


def test_contexts_learn_separate_preferences():
    policy = app.AdaptivePolicy()
    rate(policy, "technical", "not_helpful")
    rate(policy, "technical", "helpful")
    rate(policy, "billing", "helpful")
    rate(policy, "billing", "not_helpful")
    assert policy.select("technical")[0] == "guided"
    assert policy.select("billing")[0] == "brief"


def test_newer_negative_feedback_can_change_previous_preference():
    policy = app.AdaptivePolicy()
    rate(policy, "technical", "not_helpful")
    rate(policy, "technical", "helpful")
    assert rate(policy, "technical", "not_helpful").scores_after["guided"] == 0.375
    assert policy.select("technical")[0] == "guided"
    assert rate(policy, "technical", "not_helpful").scores_after["guided"] == 0.1875
    assert policy.select("technical")[0] == "brief"


def test_duplicate_feedback_cannot_change_scores_twice():
    policy = app.AdaptivePolicy()
    answer = app.respond("Issue", "technical", policy)
    policy.feedback(answer.episode_id, "helpful")
    before = policy.statistics("technical")
    with pytest.raises(ValueError, match="already recorded"):
        policy.feedback(answer.episode_id, "not_helpful")
    assert policy.statistics("technical") == before


@pytest.mark.parametrize("rating", ["bad", "", None, True, 1])
def test_invalid_rating_does_not_consume_feedback(rating):
    policy = app.AdaptivePolicy()
    answer = app.respond("Issue", "technical", policy)
    with pytest.raises(ValueError, match="Rating"):
        policy.feedback(answer.episode_id, rating)
    assert policy.scores("technical") == {"brief": 0.5, "guided": 0.5}
    assert policy.feedback(answer.episode_id, "helpful").scores_after["brief"] == 0.75


@pytest.mark.parametrize("identifier", [0, 999, True, "1", None])
def test_unknown_feedback_id_rejected(identifier):
    with pytest.raises(ValueError, match="episode"):
        app.AdaptivePolicy().feedback(identifier, "helpful")


def test_feedback_is_attributed_to_original_context_and_strategy():
    policy = app.AdaptivePolicy()
    technical = app.respond("Issue", "technical", policy)
    billing = app.respond("Issue", "billing", policy)
    policy.feedback(billing.episode_id, "helpful")
    policy.feedback(technical.episode_id, "not_helpful")
    assert policy.scores("billing")["brief"] == 0.75
    assert policy.scores("technical")["brief"] == 0.25


def test_reset_invalidates_context_episodes_but_preserves_other_context():
    policy = app.AdaptivePolicy()
    technical = app.respond("Issue", "technical", policy)
    billing = app.respond("Issue", "billing", policy)
    policy.feedback(technical.episode_id, "helpful")
    policy.reset("technical")
    assert policy.scores("technical") == {"brief": 0.5, "guided": 0.5}
    with pytest.raises(ValueError, match="reset episode"):
        policy.feedback(technical.episode_id, "helpful")
    assert policy.feedback(billing.episode_id, "helpful").scores_after["brief"] == 0.75


def test_episode_limit_is_checked_before_generation_and_not_recycled_by_reset():
    policy = app.AdaptivePolicy(max_episodes=1)
    answer = app.respond("Issue", "technical", policy)
    policy.reset("technical")
    with pytest.raises(ValueError, match="Episode limit"):
        app.respond("Issue", "technical", policy, responder=lambda *_: pytest.fail("must not generate"))
    assert answer.episode_id == 1


def test_tie_prefers_brief_after_both_strategies_have_feedback():
    policy = app.AdaptivePolicy()
    rate(policy, "billing", "helpful")
    rate(policy, "billing", "helpful")
    assert policy.scores("billing") == {"brief": 0.75, "guided": 0.75}
    assert policy.select("billing")[0] == "brief"


def test_statistics_and_results_are_not_mutable_policy_state():
    policy = app.AdaptivePolicy()
    stats = policy.statistics("technical")
    stats["brief"].score = 99
    result = app.respond("Issue", "technical", policy)
    result.scores_before["brief"] = 99
    assert policy.scores("technical")["brief"] == 0.5


@pytest.mark.parametrize("reply", [None, "text", app.Reply("guided", "Ack", ["one", "two"]),
    app.Reply("brief", "", ["step"]), app.Reply("brief", "Ack", []),
    app.Reply("brief", "Ack", ["one", "two"]), app.Reply("brief", "Ack", [None]),
    app.Reply("brief", "Ack\nextra", ["step"]), app.Reply("brief", "Ack", ["step\nextra"]),
    app.Reply("brief", "a" * 201, ["step"]), app.Reply("brief", "Ack", ["s" * 301])])
def test_invalid_reply_does_not_record_episode_or_update_policy(reply):
    policy = app.AdaptivePolicy(max_episodes=1)
    with pytest.raises(ValueError, match="Reply"):
        app.respond("Issue", "technical", policy, responder=lambda *_: reply)
    assert policy.scores("technical") == {"brief": 0.5, "guided": 0.5}
    assert app.respond("Issue", "technical", policy).episode_id == 1


def test_responder_exception_does_not_record_episode():
    policy = app.AdaptivePolicy(max_episodes=1)
    def broken(*args):
        raise RuntimeError("unavailable")
    with pytest.raises(RuntimeError):
        app.respond("Issue", "technical", policy, responder=broken)
    assert app.respond("Issue", "technical", policy).episode_id == 1


@pytest.mark.parametrize("query,context", [("", "technical"), (None, "technical"),
    ("x" * 1001, "technical"), ("Issue", "unknown"), ("Issue", None)])
def test_invalid_input_rejected_before_generation(query, context):
    with pytest.raises(ValueError):
        app.respond(query, context, app.AdaptivePolicy(), responder=lambda *_: pytest.fail("must validate first"))


@pytest.mark.parametrize("options", [{"learning_rate": 0}, {"learning_rate": -1},
    {"learning_rate": 1.1}, {"learning_rate": float("nan")}, {"learning_rate": True},
    {"max_episodes": 0}, {"max_episodes": 101}, {"max_episodes": True}])
def test_invalid_configuration(options):
    with pytest.raises(ValueError):
        app.AdaptivePolicy(**options)


def test_custom_learning_rate_updates_score_as_documented():
    policy = app.AdaptivePolicy(learning_rate=0.2)
    result = rate(policy, "technical", "helpful")
    assert result.scores_after["brief"] == pytest.approx(0.6)
