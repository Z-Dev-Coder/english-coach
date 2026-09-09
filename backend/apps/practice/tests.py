import random

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ai.providers.base import AIProvider, AIResult, AIUnavailable
from apps.practice.models import SpeakingScript
from apps.practice.scripts import (
    TEMPLATES,
    _expressions_for,
    build_portable_prompt,
    generate_ai_script,
    generate_template_script,
)
from apps.practice.services import create_speaking_script

User = get_user_model()


class TemplateScriptTests(TestCase):
    def test_generates_without_any_ai(self):
        script = generate_template_script(scenario=None, level="B1", rng=random.Random(0))
        self.assertEqual(script["source"], "template")
        self.assertTrue(script["title"])
        self.assertTrue(script["target_expressions"])
        self.assertTrue(script["portable_prompt"])

    def test_requested_scenario_is_honoured(self):
        script = generate_template_script(scenario="job_interview", level="B1")
        self.assertEqual(script["scenario"], "job_interview")

    def test_unknown_scenario_still_returns_something_usable(self):
        script = generate_template_script(scenario="underwater_basket_weaving", level="B1")
        self.assertTrue(script["portable_prompt"])

    def test_expressions_never_exceed_the_learners_level(self):
        # "Catching up with a friend" has A1/B1/B2 sets but no A2 set, so an A2
        # learner must fall back to A1 rather than being handed B1 material.
        template = next(t for t in TEMPLATES if t.title == "Catching up with a friend")
        self.assertEqual(_expressions_for(template, "A1"), template.expressions["A1"])
        self.assertEqual(_expressions_for(template, "A2"), template.expressions["A1"])
        self.assertEqual(_expressions_for(template, "B1"), template.expressions["B1"])
        self.assertEqual(_expressions_for(template, "C2"), template.expressions["B2"])

    def test_exact_level_match_is_preferred_over_a_lower_one(self):
        template = next(t for t in TEMPLATES if "B1" in t.expressions)
        self.assertEqual(_expressions_for(template, "B1"), template.expressions["B1"])

    def test_learner_below_every_set_gets_the_easiest_one(self):
        template = next(t for t in TEMPLATES if "A1" not in t.expressions)
        easiest = min(template.expressions)
        self.assertEqual(_expressions_for(template, "A1"), template.expressions[easiest])


class PortablePromptTests(TestCase):
    """The pasteable prompt is the whole point of this feature, so its contract
    is tested explicitly rather than assumed."""

    def _prompt(self, level="B1"):
        return build_portable_prompt(
            title="T",
            setting="You are at a cafe.",
            goal="Order a drink.",
            level=level,
            expressions=["Could I get...", "No rush"],
            questions=["What do you usually order?"],
        )

    def test_states_the_level_and_expected_partner_behaviour(self):
        prompt = self._prompt("A2")
        self.assertIn("CEFR A2", prompt)
        self.assertIn("keep vocabulary basic", prompt)

    def test_higher_level_asks_for_harder_english(self):
        self.assertIn("natural speed", self._prompt("B2"))

    def test_includes_the_target_expressions_and_the_situation(self):
        prompt = self._prompt()
        self.assertIn("Could I get...", prompt)
        self.assertIn("You are at a cafe.", prompt)

    def test_forbids_mid_roleplay_correction(self):
        self.assertIn("Do NOT correct my English during the roleplay", self._prompt())

    def test_defines_the_feedback_trigger(self):
        prompt = self._prompt()
        self.assertIn('"FEEDBACK"', prompt)
        self.assertIn("natural version", prompt)

    def test_is_self_contained_and_pasteable(self):
        prompt = self._prompt()
        self.assertTrue(prompt.startswith("You are my English speaking partner"))
        self.assertIn("Begin now", prompt)

    def test_unknown_level_falls_back_to_b1_guidance(self):
        prompt = build_portable_prompt(
            title="T", setting="s", goal="g", level="ZZ", expressions=[], questions=[]
        )
        self.assertIn("unhurried pace", prompt)


class _BrokenProvider(AIProvider):
    name = "broken"

    def generate(self, prompt, **kwargs):
        raise AIUnavailable("model is not installed")

    def chat(self, messages, **kwargs):
        raise AIUnavailable("model is not installed")

    def health(self):
        return {"reachable": False}


class _StubProvider(AIProvider):
    name = "stub"

    def generate(self, prompt, **kwargs):
        return AIResult(
            text=(
                '{"title": "Tech standup", "setting": "A daily standup.", "goal": "Give an update.",'
                ' "target_expressions": ["I ran into an issue"],'
                ' "lines": [{"speaker": "Partner", "text": "What did you work on?"}],'
                ' "follow_up_questions": ["What is blocking you?"]}'
            ),
            model="stub",
            tier="medium",
            duration_ms=1,
        )

    def chat(self, messages, **kwargs):
        return self.generate("")

    def health(self):
        return {"reachable": True}


class AIScriptTests(TestCase):
    def test_ai_script_is_used_when_the_model_answers(self):
        script = generate_ai_script(_StubProvider(), scenario="workplace", level="B2")
        self.assertEqual(script["source"], "ai")
        self.assertEqual(script["title"], "Tech standup")
        self.assertIn("I ran into an issue", script["portable_prompt"])

    def test_falls_back_to_a_template_when_the_model_is_down(self):
        script = generate_ai_script(_BrokenProvider(), scenario="workplace", level="B1")
        self.assertEqual(script["source"], "template")
        self.assertTrue(script["portable_prompt"])


class SpeakingScriptServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password="pw-for-tests-123")

    def test_script_is_pitched_at_the_speaking_level_not_the_overall_one(self):
        # Strong reader, weak speaker: the script must follow speaking.
        self.user.skill_progress.filter(skill="reading").update(level="C1", score=90)
        self.user.skill_progress.filter(skill="speaking").update(level="A2", score=30)
        script = create_speaking_script(self.user)
        self.assertEqual(script.level, "A2")

    def test_explicit_level_overrides_the_profile(self):
        self.assertEqual(create_speaking_script(self.user, level="C1").level, "C1")

    def test_script_is_persisted_for_the_owning_user(self):
        create_speaking_script(self.user, scenario="restaurant")
        script = SpeakingScript.objects.get(user=self.user)
        self.assertEqual(script.scenario, "restaurant")
        self.assertEqual(script.times_practiced, 0)
