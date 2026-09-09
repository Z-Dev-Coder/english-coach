from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("sessions", views.StudySessionViewSet, basename="session")
router.register(
    "practice/speaking-scripts", views.SpeakingScriptViewSet, basename="speaking-script"
)

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("lessons/today/", views.TodayLessonView.as_view(), name="today-lesson"),
    path("ai/status/", views.ai_status, name="ai-status"),
    path("meta/", views.meta, name="meta"),
    path("", include(router.urls)),
]
