"""Word lookup: normalisation, inflection guessing, parsing, caching.

The network is mocked everywhere. A test suite that reaches dictionaryapi.dev
would be slow, would fail offline, and would start failing on someone else's
schedule -- and the thing actually worth testing is our handling of what comes
back, not that the internet exists.
"""
from unittest import mock

from django.test import TestCase

from apps.vocabulary import lookup
from apps.vocabulary.dictionary import (
    candidate_forms,
    clean_text,
    normalize_word,
    parse_entries,
    parse_wiktionary,
)
from apps.vocabulary.models import Expression, WordDefinition


class NormalizeWordTests(TestCase):
    def test_strips_the_punctuation_that_comes_with_a_click(self):
        # A click in running text lands on a token, not on a lemma.
        for raw, expected in [
            ("commute.", "commute"),
            ('"nightmare,"', "nightmare"),
            ("Commute", "commute"),
            ("(annoying)", "annoying"),
            ("well-being", "well-being"),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_word(raw), expected)

    def test_drops_possessives_but_keeps_contractions_readable(self):
        self.assertEqual(normalize_word("commuter's"), "commuter")
        # Curly apostrophes are what smart-quoted copy actually contains.
        self.assertEqual(normalize_word("commuter’s"), "commuter")
        self.assertEqual(normalize_word("don't"), "dont")

    def test_rejects_things_that_are_not_words(self):
        # A phrase is rejected rather than concatenated: stripping spaces along
        # with the punctuation would turn it into a nonsense key that misses,
        # gets cached, and costs a request on the way.
        for raw in ["", "   ", "123", "!!!", "—", "a bit of a nightmare", "two words"]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_word(raw), "")


class CandidateFormsTests(TestCase):
    def test_tries_the_word_as_written_first(self):
        self.assertEqual(candidate_forms("commute")[0], "commute")

    def test_offers_base_forms_for_regular_inflections(self):
        self.assertIn("commute", candidate_forms("commuting"))
        self.assertIn("commute", candidate_forms("commuted"))
        self.assertIn("commute", candidate_forms("commutes"))
        self.assertIn("stop", candidate_forms("stopping"))
        self.assertIn("stop", candidate_forms("stopped"))
        self.assertIn("story", candidate_forms("stories"))

    def test_never_offers_a_fragment(self):
        # A one-letter candidate cannot be a word and would waste a request.
        for word in ["is", "as", "ing", "ed"]:
            with self.subTest(word=word):
                self.assertTrue(all(len(form) >= 2 for form in candidate_forms(word)))


class CleanTextTests(TestCase):
    def test_unescapes_before_stripping_tags(self):
        # Stripping first would leave "<b>bold</b>" as literal visible markup.
        self.assertEqual(clean_text("&lt;b&gt;bold&lt;/b&gt;", 100), "bold")

    def test_removes_markup_and_collapses_whitespace(self):
        self.assertEqual(clean_text("<p>a  <i>test</i>\n\n</p>", 100), "a test")

    def test_removes_control_and_direction_characters(self):
        # A bidi override can make stored text display as something else.
        self.assertEqual(clean_text("safe‮txet‬", 100), "safetxet")

    def test_removes_stylesheets_rather_than_just_their_tags(self):
        # Wiktionary embeds these inside definitions. Stripping only the tags
        # left "A very unpleasant dream .mw-parser-output ..." on screen.
        raw = "A very unpleasant dream<style>.mw-parser-output{color:red}</style>"
        self.assertEqual(clean_text(raw, 200), "A very unpleasant dream")

    def test_tidies_the_spacing_that_tag_removal_leaves(self):
        # Tags become spaces, so punctuation that followed one is left adrift.
        self.assertEqual(clean_text("a dream</span>.", 100), "a dream.")
        self.assertEqual(clean_text("a dream<b></b>. .", 100), "a dream.")

    def test_caps_length(self):
        self.assertEqual(len(clean_text("x" * 500, 20)), 20)

    def test_non_strings_are_empty_rather_than_an_error(self):
        for value in [None, 12, {"a": 1}, []]:
            with self.subTest(value=value):
                self.assertEqual(clean_text(value, 50), "")


class ParseEntriesTests(TestCase):
    PAYLOAD = [
        {
            "word": "commute",
            "phonetic": "/kəˈmjuːt/",
            "meanings": [
                {
                    "partOfSpeech": "verb",
                    "definitions": [
                        {
                            "definition": "To travel regularly between home and work.",
                            "example": "She commutes by train.",
                        }
                    ],
                }
            ],
        }
    ]

    def test_parses_a_normal_entry(self):
        [entry] = parse_entries(self.PAYLOAD, word="commute")
        self.assertEqual(entry["phonetic"], "/kəˈmjuːt/")
        self.assertEqual(entry["senses"][0]["part_of_speech"], "verb")
        self.assertIn("travel regularly", entry["senses"][0]["definition"])

    def test_survives_every_shape_the_api_actually_returns(self):
        # Each of these has been observed from dictionaryapi.dev. None may
        # raise: a broken lookup must not break the page it was hovered on.
        for payload in [
            None,
            {},
            [],
            ["not a dict"],
            [{"meanings": None}],
            [{"meanings": [{"definitions": [{}]}]}],
            [{"meanings": [{"definitions": [{"definition": ""}]}]}],
            [{"meanings": [{"definitions": "wrong type"}]}],
        ]:
            with self.subTest(payload=payload):
                self.assertEqual(parse_entries(payload, word="x"), [])

    def test_falls_back_to_the_phonetics_list(self):
        payload = [
            {
                "phonetics": [{"text": "/tɛst/"}],
                "meanings": [
                    {"partOfSpeech": "noun", "definitions": [{"definition": "A trial."}]}
                ],
            }
        ]
        [entry] = parse_entries(payload, word="test")
        self.assertEqual(entry["phonetic"], "/tɛst/")

    def test_caps_the_number_of_senses(self):
        payload = [
            {
                "meanings": [
                    {
                        "partOfSpeech": "noun",
                        "definitions": [{"definition": f"Sense {i}."} for i in range(20)],
                    }
                ]
            }
        ]
        [entry] = parse_entries(payload, word="x")
        self.assertLessEqual(len(entry["senses"]), 4)


class ParseWiktionaryTests(TestCase):
    def test_strips_wiki_markup_from_definitions(self):
        payload = {
            "en": [
                {
                    "partOfSpeech": "Verb",
                    "definitions": [
                        {
                            "definition": 'To <a rel="mw:WikiLink" href="/wiki/travel">travel</a> regularly.',
                            "examples": ["She <b>commutes</b> by train."],
                        }
                    ],
                }
            ]
        }
        [entry] = parse_wiktionary(payload, word="commute")
        self.assertEqual(entry["senses"][0]["definition"], "To travel regularly.")
        self.assertEqual(entry["senses"][0]["example"], "She commutes by train.")
        self.assertEqual(entry["senses"][0]["part_of_speech"], "verb")

    def test_skips_entries_that_are_markup_only(self):
        # Real responses contain definitions that are a label span and nothing
        # else; those clean down to an empty string and must not become senses.
        payload = {
            "en": [
                {
                    "partOfSpeech": "Noun",
                    "definitions": [
                        {"definition": '<span class="usage-label-sense"></span>'},
                        {"definition": "A regular journey."},
                    ],
                }
            ]
        }
        [entry] = parse_wiktionary(payload, word="commute")
        self.assertEqual(len(entry["senses"]), 1)
        self.assertEqual(entry["senses"][0]["definition"], "A regular journey.")

    def test_ignores_other_languages(self):
        # The same spelling often exists in French or German on that endpoint.
        payload = {"fr": [{"partOfSpeech": "Nom", "definitions": [{"definition": "Trajet."}]}]}
        self.assertEqual(parse_wiktionary(payload, word="commute"), [])

    def test_survives_malformed_payloads(self):
        for payload in [None, [], "text", {"en": None}, {"en": ["x"]}, {"en": [{}]}]:
            with self.subTest(payload=payload):
                self.assertEqual(parse_wiktionary(payload, word="x"), [])


class LookUpTests(TestCase):
    def setUp(self):
        # The failure cooldown is module-level state, so it outlives a test.
        # Without this reset, a test that simulates an outage leaves the source
        # marked down and the next test silently skips it.
        lookup._last_failure.clear()

    def test_prefers_our_own_expression_over_the_dictionary(self):
        # Our meaning is written at the learner's level and carries register,
        # so it should win -- and it should cost no request at all.
        Expression.objects.create(
            text="nightmare",
            meaning="Something that was difficult or annoying.",
            part_of_speech="noun",
        )
        with mock.patch("apps.vocabulary.lookup._fetch") as fetch:
            result = lookup.look_up("nightmare")
        fetch.assert_not_called()
        self.assertEqual(result["source"], "app")
        self.assertIn("annoying", result["entries"][0]["senses"][0]["definition"])

    def test_fetches_once_then_serves_from_cache(self):
        entries = [{"word": "commute", "phonetic": "", "senses": [{"definition": "To travel."}]}]
        with mock.patch("apps.vocabulary.lookup._fetch", return_value=entries) as fetch:
            lookup.look_up("commute")
            lookup.look_up("Commute.")  # same word, different token
        self.assertEqual(fetch.call_count, 1)

    def test_caches_misses_too(self):
        # Otherwise every hover on a name re-hits the network, which is the
        # common case rather than the rare one.
        with mock.patch("apps.vocabulary.lookup._fetch", return_value=[]) as fetch:
            first = lookup.look_up("zzzqqq")
            second = lookup.look_up("zzzqqq")
        self.assertEqual(fetch.call_count, 1)
        self.assertFalse(first["found"])
        self.assertFalse(second["found"])
        self.assertTrue(WordDefinition.objects.filter(word="zzzqqq").exists())

    def test_falls_back_to_a_base_form(self):
        def fake_fetch(word):
            return (
                [{"word": "commute", "phonetic": "", "senses": [{"definition": "To travel."}]}]
                if word == "commute"
                else []
            )

        with mock.patch("apps.vocabulary.lookup._fetch", side_effect=fake_fetch):
            result = lookup.look_up("commuting")
        self.assertTrue(result["found"])
        self.assertEqual(result["word"], "commute")

    def test_a_token_that_is_not_a_word_costs_no_request(self):
        with mock.patch("apps.vocabulary.lookup._fetch") as fetch:
            result = lookup.look_up("—")
        fetch.assert_not_called()
        self.assertFalse(result["found"])

    def test_network_failure_is_a_miss_not_an_exception(self):
        import requests

        with mock.patch(
            "apps.vocabulary.lookup.requests.get",
            side_effect=requests.ConnectionError("offline"),
        ):
            result = lookup.look_up("commute")
        self.assertFalse(result["found"])

    def test_an_unreachable_source_is_never_cached_as_a_miss(self):
        """The bug this guards against was live for one commit.

        Every source timing out was recorded as "no such word", so a single
        flaky minute left common words permanently undefined -- and because
        misses are cached deliberately, nothing would ever retry them.
        """
        import requests

        with mock.patch(
            "apps.vocabulary.lookup.requests.get",
            side_effect=requests.Timeout("slow"),
        ):
            result = lookup.look_up("commute")

        self.assertEqual(result["source"], "unavailable")
        self.assertFalse(WordDefinition.objects.filter(word="commute").exists())

        # And once the network is back, the word resolves normally.
        entries = [{"word": "commute", "phonetic": "", "senses": [{"definition": "To travel."}]}]
        with mock.patch("apps.vocabulary.lookup._fetch", return_value=entries):
            self.assertTrue(lookup.look_up("commute")["found"])

    def test_a_genuine_404_from_every_source_is_cached_as_a_miss(self):
        # The opposite case: the sources answered, and nobody knows the word.
        with mock.patch(
            "apps.vocabulary.lookup.requests.get",
            return_value=mock.Mock(status_code=404),
        ):
            result = lookup.look_up("zzzqqq")
        self.assertEqual(result["source"], "none")
        self.assertTrue(WordDefinition.objects.filter(word="zzzqqq").exists())

    def test_falls_back_to_wiktionary_when_the_first_source_is_down(self):
        wiktionary = {
            "en": [
                {
                    "partOfSpeech": "Noun",
                    "definitions": [
                        {"definition": "A regular journey between home and work."}
                    ],
                }
            ]
        }

        def fake_get(url, **kwargs):
            if "dictionaryapi.dev" in url:
                raise requests.ConnectionError("down")
            return mock.Mock(status_code=200, json=mock.Mock(return_value=wiktionary))

        import requests

        with mock.patch("apps.vocabulary.lookup.requests.get", side_effect=fake_get):
            result = lookup.look_up("commute")

        self.assertTrue(result["found"])
        self.assertIn("regular journey", result["entries"][0]["senses"][0]["definition"])

    def test_upstream_nonsense_is_a_miss_not_an_exception(self):
        response = mock.Mock(status_code=200)
        response.json.side_effect = ValueError("not json")
        with mock.patch("apps.vocabulary.lookup.requests.get", return_value=response):
            self.assertFalse(lookup.look_up("commute")["found"])


class SourceCooldownTests(TestCase):
    """A source that just failed is skipped rather than retried.

    Without this, a source being down cost its full timeout on every single
    lookup before the working source was tried -- over four seconds per word
    for a panel that opens under the pointer.
    """

    def setUp(self):
        lookup._last_failure.clear()

    def test_a_failed_source_is_not_retried_immediately(self):
        import requests

        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            raise requests.ConnectionError("down")

        with mock.patch("apps.vocabulary.lookup.requests.get", side_effect=fake_get):
            lookup.look_up("commute")
            first_round = len(calls)
            lookup.look_up("nightmare")

        # Both sources tried once; the second word tried neither.
        self.assertEqual(first_round, 2)
        self.assertEqual(len(calls), 2)

    def test_the_cooldown_expires(self):
        import requests

        with mock.patch(
            "apps.vocabulary.lookup.requests.get", side_effect=requests.ConnectionError("down")
        ):
            lookup.look_up("commute")

        # Pretend the cooldown has passed rather than sleeping through it.
        for url in list(lookup._last_failure):
            lookup._last_failure[url] -= lookup.FAILURE_COOLDOWN + 1

        entries = [{"word": "nightmare", "phonetic": "", "senses": [{"definition": "A bad dream."}]}]
        with mock.patch("apps.vocabulary.lookup._fetch", return_value=entries) as fetch:
            result = lookup.look_up("nightmare")
        fetch.assert_called()
        self.assertTrue(result["found"])

    def test_success_clears_a_previous_failure(self):
        lookup._note_failure(lookup.WIKTIONARY_URL)
        self.assertTrue(lookup._recently_failed(lookup.WIKTIONARY_URL))
        lookup._note_success(lookup.WIKTIONARY_URL)
        self.assertFalse(lookup._recently_failed(lookup.WIKTIONARY_URL))
