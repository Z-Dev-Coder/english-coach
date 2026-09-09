from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import review_views, skills_views, views

router = DefaultRouter()
router.register("sessions", views.StudySessionViewSet, basename="session")
router.register(
    "practice/speaking-scripts", views.SpeakingScriptViewSet, basename="speaking-script"
)
router.register("vocabulary", review_views.VocabularyViewSet, basename="vocabulary")
router.register("skills/passages", skills_views.PassageViewSet, basename="passage")

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("lessons/today/", views.TodayLessonView.as_view(), name="today-lesson"),
    path("review/queue/", review_views.ReviewQueueView.as_view(), name="review-queue"),
    path("review/answer/", review_views.ReviewAnswerView.as_view(), name="review-answer"),
    path("review/stats/", review_views.ReviewStatsView.as_view(), name="review-stats"),
    path("review/history/", review_views.ReviewHistoryView.as_view(), name="review-history"),
    path("skills/dictation/", skills_views.DictationView.as_view(), name="dictation"),
    path("skills/shadowing/", skills_views.ShadowingView.as_view(), name="shadowing"),
    path("skills/writing/", skills_views.WritingView.as_view(), name="writing"),
    path("skills/reading/", skills_views.ReadingView.as_view(), name="reading"),
    path("skills/drill/", skills_views.DrillView.as_view(), name="drill"),
    path("skills/attempts/", skills_views.AttemptListView.as_view(), name="attempts"),
    path("skills/summary/", skills_views.SkillSummaryView.as_view(), name="skill-summary"),
    path("ai/status/", views.ai_status, name="ai-status"),
    path("meta/", views.meta, name="meta"),
    path("", include(router.urls)),
]
