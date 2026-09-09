"""Report what the AI has actually cost, from logged token usage.

Every provider call records its real token counts, so this prices what happened
rather than what was predicted. Run it after a week of normal study and you will
know your true rate instead of trusting anyone's estimate.
"""
import datetime as dt

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from django.utils import timezone

from apps.ai.models import AIRequestLog

# USD per 1M tokens, off-peak. Peak is exactly double.
# Source: https://api-docs.deepseek.com/quick_start/pricing/ (September 2026).
# Verify before relying on these: published rates change.
RATES = {
    "deepseek-v4-flash": {"input": 0.22, "cached": 0.007, "output": 0.66},
    "deepseek-v4-pro": {"input": 0.66, "cached": 0.022, "output": 1.98},
    "deepseek-v4-flash-vision-exp": {"input": 0.22, "cached": 0.007, "output": 0.66},
    "gpt-4o-mini": {"input": 0.15, "cached": 0.075, "output": 0.60},
    "gpt-4o": {"input": 2.50, "cached": 1.25, "output": 10.00},
}


class Command(BaseCommand):
    help = "Report real AI token usage and what it would cost on a hosted provider."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30, help="Window to report on.")
        parser.add_argument(
            "--peak",
            action="store_true",
            help="Price at peak rates (01:00-04:00 and 06:00-10:00 UTC, Mon-Fri).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        since = timezone.now() - dt.timedelta(days=days)
        logs = AIRequestLog.objects.filter(created_at__gte=since, success=True)

        if not logs.exists():
            self.stdout.write(
                "No AI calls logged yet. Use the app for a few days, then run this again.\n"
                "Local models log tokens too, so you can measure before paying anything."
            )
            return

        rows = (
            logs.values("model", "tier", "task")
            .annotate(
                calls=Count("id"),
                prompt=Sum("prompt_tokens"),
                completion=Sum("completion_tokens"),
            )
            .order_by("-calls")
        )

        multiplier = 2 if options["peak"] else 1
        active_days = (
            logs.dates("created_at", "day").count() or 1
        )

        self.stdout.write(
            f"\nAI usage over the last {days} days ({active_days} with activity)\n"
        )
        header = f"{'task':<22}{'model':<26}{'calls':>7}{'in':>10}{'out':>10}{'cost':>9}"
        self.stdout.write(header)
        self.stdout.write("-" * len(header))

        total_cost = 0.0
        total_in = total_out = 0
        unpriced = set()

        for row in rows:
            prompt = row["prompt"] or 0
            completion = row["completion"] or 0
            total_in += prompt
            total_out += completion

            rate = RATES.get(row["model"])
            if rate:
                cost = (
                    prompt / 1e6 * rate["input"] + completion / 1e6 * rate["output"]
                ) * multiplier
                total_cost += cost
                cost_text = f"${cost:.4f}"
            else:
                unpriced.add(row["model"])
                cost_text = "free"

            self.stdout.write(
                f"{row['task'][:21]:<22}{row['model'][:25]:<26}"
                f"{row['calls']:>7}{prompt:>10}{completion:>10}{cost_text:>9}"
            )

        self.stdout.write("-" * len(header))
        self.stdout.write(
            f"{'TOTAL':<48}{total_in:>10}{total_out:>10}{'$' + format(total_cost, '.4f'):>9}"
        )

        if unpriced:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nRunning locally on {', '.join(sorted(unpriced))} — these cost nothing."
                )
            )
            self.stdout.write(
                "The token counts above are real, so they show what a hosted provider "
                "would have charged for the same work. Try --days 7 after a normal week."
            )

        if total_cost:
            per_day = total_cost / active_days
            self.stdout.write(
                f"\n  per active day   ${per_day:.4f}"
                f"\n  per month (30)   ${per_day * 30:.2f}"
                f"\n  per year (365)   ${per_day * 365:.2f}"
            )
            if not options["peak"]:
                self.stdout.write(
                    "\n  Priced off-peak. Peak hours (01:00-04:00, 06:00-10:00 UTC, Mon-Fri)"
                    "\n  cost exactly double — re-run with --peak to see the worst case."
                )

        # What a hosted provider would charge for the same real usage.
        if unpriced and total_in:
            self.stdout.write("\nIf the same work ran on a hosted provider:")
            for model, rate in RATES.items():
                if not model.startswith("deepseek"):
                    continue
                cost = (total_in / 1e6 * rate["input"] + total_out / 1e6 * rate["output"])
                per_day = cost / active_days
                self.stdout.write(
                    f"  {model:<30} ${per_day * 30:>6.2f}/month off-peak"
                    f"   (${per_day * 365:.2f}/year)"
                )
