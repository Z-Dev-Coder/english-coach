from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import review_views, views

router = DefaultRouter()
router.register("sessions", views.StudySessionViewSet, basename="session")
router.register(
    "practice/speaking-scripts", views.SpeakingScriptViewSet, basename="speaking-script"
)
router.register("vocabulary", review_views.VocabularyViewSet, basename="vocabulary")

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
    path("ai/status/", views.ai_status, name="ai-status"),
    path("meta/", views.meta, name="meta"),
    path("", include(router.urls)),
]
