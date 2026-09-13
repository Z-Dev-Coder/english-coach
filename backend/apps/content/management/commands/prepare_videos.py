"""Write lesson notes for YouTube videos from saved transcript files.

    python manage.py prepare_videos <dir>

<dir> holds one JSON transcript per video (a {"data": {"video_id", "transcript": [...]}}
response, or a bare {"video_id", "transcript"} object). The transcript is only
read to write the notes; it is not stored.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.content import videos
from apps.content.models import VideoLesson


class Command(BaseCommand):
    help = "Prepare Watch-on-YouTube lessons from transcript files."

    def add_arguments(self, parser):
        parser.add_argument("directory")
        parser.add_argument("--force", action="store_true", help="Re-prepare videos that already have notes.")

    def handle(self, *args, directory, force, **options):
        videos.ensure_library()
        ready = 0
        for path in sorted(Path(directory).glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            data = payload.get("data", payload)
            video = VideoLesson.objects.filter(video_id=data.get("video_id")).first()
            if video is None:
                self.stderr.write(f"{path.name}: video not in the library")
                continue
            if video.prepared_at and not force:
                continue
            if videos.prepare(video, videos.timed_text(data.get("transcript") or [])):
                ready += 1
                self.stdout.write(f"+ [{video.level}] {video.title}")
            else:
                self.stderr.write(f"{path.name}: preparation failed")
        self.stdout.write(self.style.SUCCESS(f"Prepared {ready} video lessons."))
