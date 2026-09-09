"""Tests for the conversation tutor.

The rule under test throughout: talk first, correct afterwards.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ai.providers.base import AIProvider, AIResult, AIUnavailable
from apps.conversation import services
from apps.conversation.models import ConversationMessage, ConversationSession
from apps.profiles.constants import Skill
from apps.profiles.models import SkillProgress

User = get_user_model()
PASSWORD = "pw-for-tests-123"

FEEDBACK_JSON = (
    '{"summary": "A relaxed conversation that kept going.",'
    ' "estimated_level": "B1",'
    ' "did_well": ["You used \'deal with\' naturally."],'
    ' "corrections": [{"original": "I very like it", "natural": "I really like it",'
    '   "explanation": "\'Very\' does not modify verbs.", "category": "word_choice"}],'
    ' "useful_expressions": ["to be honest"],'
    ' "focus_next_time": "Watch adverb placement."}'
)


class ChatProvider(AIProvider):
    """Records what it was asked and returns scripted replies."""

    name = "chat-stub"

    def __init__(self, chat_reply="So what happened next?", json_reply=FEEDBACK_JSON):
        self.chat_reply = chat_reply
        self.json_reply = json_reply
        self.chat_calls = []
        self.generate_calls = []

    def chat(self, messages, **kwargs):
        self.chat_calls.append(messages)
        return AIResult(text=self.chat_reply, model="stub", tier="medium", duration_ms=1)

    def generate(self, prompt, **kwargs):
        self.generate_calls.append(prompt)
        return AIResult(text=self.json_reply, model="stub", tier="medium", duration_ms=1)

    def health(self):
        return {"reachable": True}


class StartTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="conv", password=PASSWORD)

    def test_the_partner_speaks_first(self):
        """Facing an empty box is the hardest moment in speaking practice."""
        with mock.patch("apps.conversation.services.get_ai_provider", return_value=ChatProvider("Hey! How's it going?")):
            session = services.start(self.user, scenario="casual")
        first = session.messages.first()
        self.assertEqual(first.role, ConversationMessage.Role.PARTNER)
        self.assertEqual(first.content, "Hey! How's it going?")

    def test_a_conversation_can_start_with_the_model_offline(self):
        with mock.patch("apps.conversation.services.get_ai_provider", side_effect=AIUnavailable("down")):
            session = services.start(self.user, scenario="job_interview")
        self.assertEqual(session.messages.count(), 1)
        self.assertIn("tell me a bit about yourself", session.messages.first().content)

    def test_the_level_follows_speaking_not_the_best_skill(self):
        SkillProgress.objects.filter(user=self.user, skill=Skill.SPEAKING).update(level="A2")
        SkillProgress.objects.filter(user=self.user, skill=Skill.READING).update(level="C1")
        with mock.patch("apps.conversation.services.get_ai_provider", side_effect=AIUnavailable("down")):
            session = services.start(self.user)
        self.assertEqual(session.level, "A2")

    def test_an_explicit_level_wins(self):
        with mock.patch("apps.conversation.services.get_ai_provider", side_effect=AIUnavailable("down")):
            self.assertEqual(services.start(self.user, level="C1").level, "C1")

    def test_every_scenario_has_an_opener(self):
        from apps.ai.prompts import SCENARIO_HINTS

        for scenario in SCENARIO_HINTS:
            with self.subTest(scenario=scenario):
                self.assertIn(scenario, services.FALLBACK_OPENERS)


class ReplyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reply", password=PASSWORD)
        self.provider = ChatProvider()
        with mock.patch("apps.conversation.services.get_ai_provider", return_value=self.provider):
            self.session = services.start(self.user)

    def test_both_turns_are_recorded(self):
        with mock.patch("apps.conversation.services.get_ai_provider", return_value=self.provider):
            services.reply(self.session, "I went to the shops.")
        roles = list(self.session.messages.values_list("role", flat=True))
        self.assertEqual(roles, ["partner", "learner", "partner"])

    def test_the_partner_is_told_not_to_correct_mid_conversation(self):
        with mock.patch("apps.conversation.services.get_ai_provider", return_value=self.provider):
            services.reply(self.session, "I very like this.")
        system = self.provider.chat_calls[-1][0]["content"]
        self.assertIn("Do NOT correct", system)

    def test_history_is_sent_so_the_partner_stays_coherent(self):
        with mock.patch("apps.conversation.services.get_ai_provider", return_value=self.provider):
            services.reply(self.session, "First thing.")
            services.reply(self.session, "Second thing.")
        sent = self.provider.chat_calls[-1]
        contents = [message["content"] for message in sent]
        self.assertIn("First thing.", contents)
        self.assertIn("Second thing.", contents)

    def test_history_is_capped(self):
        with mock.patch("apps.conversation.services.get_ai_provider", return_value=self.provider):
            for index in range(20):
                services.reply(self.session, f"Turn {index}.")
            sent = self.provider.chat_calls[-1]
        # One system message plus at most HISTORY_TURNS of conversation.
        self.assertLessEqual(len(sent), services.HISTORY_TURNS + 1)

    def test_an_empty_model_reply_is_reported_rather_than_stored(self):
        with mock.patch("apps.conversation.services.get_ai_provider", return_value=ChatProvider(chat_reply="   ")):
            with self.assertRaises(AIUnavailable):
                services.reply(self.session, "Anything.")

    def test_the_learner_turn_survives_a_failed_reply(self):
        """What they said is theirs, and must not be lost because the model
        failed to answer."""
        before = self.session.messages.count()
        with mock.patch("apps.conversation.services.get_ai_provider", return_value=ChatProvider(chat_reply="")):
            with self.assertRaises(AIUnavailable):
                services.reply(self.session, "I said something.")
        self.assertEqual(self.session.messages.count(), before + 1)


class FeedbackTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="fb", password=PASSWORD)
        self.provider = ChatProvider()
        with mock.patch("apps.conversation.services.get_ai_provider", return_value=self.provider):
            self.session = services.start(self.user)
            services.reply(self.session, "I very like this movie.")
            services.reply(self.session, "I discussed about it with my friend.")

    def test_feedback_is_structured_and_stored(self):
        with mock.patch("apps.conversation.services.get_ai_provider", return_value=self.provider):
            feedback = services.generate_feedback(self.session)
        self.assertTrue(feedback["available"])
        self.assertEqual(feedback["corrections"][0]["natural"], "I really like it")
        self.session.refresh_from_db()
        self.assertEqual(self.session.feedback["summary"], feedback["summary"])

    def test_only_the_learners_own_words_are_reviewed(self):
        """Sending the partner's replies would invite the model to critique its
        own output."""
        with mock.patch("apps.conversation.services.get_ai_provider", return_value=self.provider):
            services.generate_feedback(self.session)
        prompt = self.provider.generate_calls[-1]
        self.assertIn("I very like this movie.", prompt)
        self.assertNotIn("So what happened next?", prompt)

    def test_feedback_degrades_without_blowing_up(self):
        with mock.patch("apps.conversation.services.get_ai_provider", side_effect=AIUnavailable("down")):
            feedback = services.generate_feedback(self.session)
        self.assertFalse(feedback["available"])
        self.assertIn("2 times", feedback["summary"])

    def test_a_conversation_with_no_learner_turns_says_so_kindly(self):
        with mock.patch("apps.conversation.services.get_ai_provider", side_effect=AIUnavailable("down")):
            empty = services.start(self.user)
            feedback = services.generate_feedback(empty)
        self.assertTrue(feedback["available"])
        self.assertEqual(feedback["corrections"], [])
        self.assertIn("even in one short sentence", feedback["focus_next_time"])


class EndTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="endy", password=PASSWORD)

    def _conversation(self, turns):
        provider = ChatProvider()
        with mock.patch("apps.conversation.services.get_ai_provider", return_value=provider):
            session = services.start(self.user)
            for turn in turns:
                services.reply(session, turn)
            services.end(session)
        return session

    def test_ending_closes_the_session(self):
        session = self._conversation(["Hello there."])
        session.refresh_from_db()
        self.assertEqual(session.status, ConversationSession.Status.ENDED)
        self.assertIsNotNone(session.ended_at)

    def test_speaking_and_fluency_are_credited(self):
        before = SkillProgress.objects.get(user=self.user, skill=Skill.SPEAKING).score
        self._conversation(["I went to the shops today.", "It was quite busy actually."])
        self.assertGreater(
            SkillProgress.objects.get(user=self.user, skill=Skill.SPEAKING).score, before
        )
        self.assertGreater(
            SkillProgress.objects.get(user=self.user, skill=Skill.FLUENCY).score, 50
        )

    def test_a_longer_conversation_is_worth_more(self):
        short_user = User.objects.create_user(username="short", password=PASSWORD)
        long_user = User.objects.create_user(username="long", password=PASSWORD)
        provider = ChatProvider()

        with mock.patch("apps.conversation.services.get_ai_provider", return_value=provider):
            brief = services.start(short_user)
            services.reply(brief, "Yes.")
            services.end(brief)

            lengthy = services.start(long_user)
            for _ in range(6):
                services.reply(lengthy, "I went into town and ended up staying much longer than planned.")
            services.end(lengthy)

        self.assertGreater(
            SkillProgress.objects.get(user=long_user, skill=Skill.SPEAKING).score,
            SkillProgress.objects.get(user=short_user, skill=Skill.SPEAKING).score,
        )

    def test_saying_nothing_earns_nothing(self):
        with mock.patch("apps.conversation.services.get_ai_provider", side_effect=AIUnavailable("down")):
            session = services.start(self.user)
            services.end(session)
        self.assertEqual(
            SkillProgress.objects.get(user=self.user, skill=Skill.SPEAKING).score, 50
        )
