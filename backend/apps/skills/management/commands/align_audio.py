"""Add real word timings to recorded passages and scenes that don't have them.

    python manage.py align_audio

New VOA passages and scenes are aligned automatically in the background; this
is for content imported before that, or to retry failures.
"""
from django.core.management.base import BaseCommand

from apps.content.models import Scene
from apps.skills import alignment
from apps.skills.models import Passage


class Command(BaseCommand):
    help = "Transcribe real recordings once and store word timings for the read-along highlight."

    def handle(self, *args, **options):
        done = 0
        for passage in Passage.objects.exclude(audio_url="").filter(word_timings=[]):
            ok = alignment.align_passage(passage)
            done += ok
            self.stdout.write(f"{'+' if ok else '-'} passage {passage.id} {passage.title[:60]}")
        for scene in Scene.objects.exclude(audio_url="").filter(word_timings=[]):
            ok = alignment.align_scene(scene)
            done += ok
            self.stdout.write(f"{'+' if ok else '-'} scene {scene.id} {scene.title[:60]}")
        self.stdout.write(self.style.SUCCESS(f"Aligned {done} recordings."))
