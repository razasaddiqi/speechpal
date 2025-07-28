from django.urls import path
from . import views

urlpatterns = [
    # User profile and progress
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('progress/', views.ProgressSummaryView.as_view(), name='progress-summary'),
    
    # Character customization
    path('character/', views.CharacterCustomizationView.as_view(), name='character-customization'),
    path('character/options/', views.CharacterCustomizationOptionsView.as_view(), name='customization-options'),
    
    # Speech sessions and analysis
    path('sessions/', views.SpeechSessionListCreateView.as_view(), name='speech-sessions'),
    path('analyze/', views.analyze_speech, name='analyze-speech'),
    
    # Achievements
    path('achievements/', views.UserAchievementsView.as_view(), name='user-achievements'),
    
    # Exercises
    path('exercises/', views.AvailableExercisesView.as_view(), name='available-exercises'),
    path('exercises/attempt/', views.ExerciseAttemptCreateView.as_view(), name='exercise-attempt'),
] 