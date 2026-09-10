from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import content_views, lesson_views, review_views, skills_views, views

router = DefaultRouter()
router.register("sessions", views.StudySessionViewSet, basename="session")
router.register(
    "practice/speaking-scripts", views.SpeakingScriptViewSet, basename="speaking-script"
)
router.register("vocabulary", review_views.VocabularyViewSet, basename="vocabulary")
router.register("skills/passages", skills_views.PassageViewSet, basename="passage")
router.register("lessons", lesson_views.LessonViewSet, basename="lesson")
router.register("conversations", lesson_views.ConversationViewSet, basename="conversation")
router.register("articles", content_views.ArticleViewSet, basename="article")
router.register("mistakes", content_views.MistakeViewSet, basename="mistake")

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    # The plan (time allocation) and the lesson (concrete activities) are
    # separate resources: the plan is cheap and always available, the lesson is
    # generated and stateful.
    path("plan/today/", views.TodayLessonView.as_view(), name="today-lesson"),
    path("learner-context/", lesson_views.LearnerContextView.as_view(), name="learner-context"),
    path("vocabulary/define/", review_views.DefineView.as_view(), name="define"),
    path("review/queue/", review_views.ReviewQueueView.as_view(), name="review-queue"),
    path("review/answer/", review_views.ReviewAnswerView.as_view(), name="review-answer"),
    path("review/stats/", review_views.ReviewStatsView.as_view(), name="review-stats"),
    path("review/history/", review_views.ReviewHistoryView.as_view(), name="review-history"),
    path("skills/dictation/", skills_views.DictationView.as_view(), name="dictation"),
    path(
        "skills/speaking-support/",
        skills_views.SpeakingSupportView.as_view(),
        name="speaking-support",
    ),
    path("skills/shadowing/", skills_views.ShadowingView.as_view(), name="shadowing"),
    path(
        "skills/shadowing/guide/",
        skills_views.ShadowingGuideView.as_view(),
        name="shadowing-guide",
    ),
    path("skills/writing/", skills_views.WritingView.as_view(), name="writing"),
    path("skills/reading/", skills_views.ReadingView.as_view(), name="reading"),
    path("skills/drill/", skills_views.DrillView.as_view(), name="drill"),
    path("skills/attempts/", skills_views.AttemptListView.as_view(), name="attempts"),
    path("skills/summary/", skills_views.SkillSummaryView.as_view(), name="skill-summary"),
    path("content/ingest/", content_views.IngestView.as_view(), name="ingest"),
    path("content/dialogue/", content_views.DialogueStudyView.as_view(), name="dialogue"),
    path("ai/status/", views.ai_status, name="ai-status"),
    path("meta/", views.meta, name="meta"),
    path("", include(router.urls)),
]
