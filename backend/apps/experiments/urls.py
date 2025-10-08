from django.urls import path
from . import views

urlpatterns = [
    path('prompts/', views.PromptTemplateListCreateView.as_view(), name='prompt-list'),
    path('prompts/<int:pk>/', views.PromptTemplateDetailView.as_view(), name='prompt-detail'),
    path('inferences/', views.InferenceListView.as_view(), name='inference-list'),
    path('runs/', views.ExperimentRunListCreateView.as_view(), name='experiment-run-list'),
    path('runs/<int:pk>/', views.ExperimentRunDetailView.as_view(), name='experiment-run-detail'),
    path('replay/', views.start_replay_experiment, name='start-replay'),
    path('compare/<str:run_id1>/<str:run_id2>/', views.experiment_comparison, name='experiment-comparison'),
    path('stats/', views.experiment_stats, name='experiment-stats'),
]
