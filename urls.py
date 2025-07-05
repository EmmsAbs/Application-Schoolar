from django.urls import path
from .views import *
from django.contrib.auth import views as auth_views

urlpatterns = [
    #path('', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('prof/', prof_dashboard, name='prof_dashboard'),
    path('etudiant/', etudiant_dashboard, name='etudiant_dashboard'),
    path('etudiant_note/', note_etudiant, name='notes_etudiant'),
    path('etudiant_bulletin/', bulletin_etudiant, name='bulletins_etudiant'),
    path('etudiant_releve/<int:annee_id>/<int:classe_id>/', releve_pdf, name='releves_pdf'),
    path("prof_notes/", tab_notes_prof, name="prof_note_list"),
    path("prof_add_notes/", add_notes_prof, name="add_note"),
    path("prof_edit_notes/<int:inscription_id>/<int:matiere_id>/", edit_notes_prof, name="edit_note"),
    path("ajax/etudiants/", get_etudiants_ajax, name="get_etudiants_ajax")
]
