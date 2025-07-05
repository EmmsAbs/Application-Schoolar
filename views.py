from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, redirect, get_object_or_404
from .utils import parse_date_safe
from .models import *
from django.contrib.auth.decorators import login_required
import csv
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.contrib import messages
from collections import defaultdict
from weasyprint import HTML
from django.template.loader import render_to_string






def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            if user.is_gestionnaire : #Gestionnaire.objects.filter(id=user.id).exists():
                return redirect('/admin/')
            elif user.is_prof : #Prof.objects.filter(id=user.id).exists():
                return redirect('prof_dashboard')
            elif user.is_etudiant : #Etudiant.objects.filter(id=user.id).exists():
                return redirect('etudiant_dashboard')
        else:
            return render(request, "core/login.html", {"error": "Identifiants invalides"})
    return render(request, "core/login.html")


@login_required
def etudiant_dashboard(request):
    if request.user.is_etudiant:
        return render(request, "core/etudiant_dashboard.html", {"user": request.user})
    return redirect("logout")


@login_required
def prof_dashboard(request):
    if request.user.is_prof:
        return render(request, "core/prof_dashboard.html", {"user": request.user})
    return redirect("logout")


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def tab_notes_prof(request):
    if not request.user.is_prof:
        return redirect("logout")

    prof = request.user.prof  # Professeur connecté

    # Récupération des filtres (valeurs ou None)
    matiere_id = request.GET.get("matiere")
    classe_id = request.GET.get("classe")
    annee_id = request.GET.get("annee")
    recherche = request.GET.get("recherche", "").strip()

    matieres = prof.matieres.all()
    classes = Classe.objects.all()
    annees = AnneeScolaire.objects.all()

    notes_finales = []

    # Objets nécessaires
    cc_types = Type.objects.filter(nom__icontains="Controle Continu")
    examen_type = Type.objects.filter(nom__icontains="Examen").first()

    # On commence par filtrer les inscriptions selon les filtres reçus
    inscriptions = Inscription.objects.all()

    if classe_id:
        inscriptions = inscriptions.filter(classe_id=classe_id)
    if annee_id:
        inscriptions = inscriptions.filter(annee_id=annee_id)

    # Filtrer les inscriptions dont l’étudiant porte le nom/prénom recherchés
    if recherche:
        inscriptions = inscriptions.filter(
            etudiant__utilisateur__first_name__icontains=recherche
        ) | inscriptions.filter(
            etudiant__utilisateur__last_name__icontains=recherche
        )

    # On filtre ensuite par matière + on récupère seulement les inscriptions dont l’étudiant a une note dans la matière
    if matiere_id:
        try:
            matiere = Matiere.objects.get(id=matiere_id)
        except Matiere.DoesNotExist:
            matiere = None
    else:
        matiere = None

    if matiere:
        inscriptions = inscriptions.filter(
            note__matiere=matiere
        ).distinct()

    # Si on a une matière, on vérifie qu’elle appartient bien au prof
    if matiere and matiere not in matieres:
        # Sécurité : matière non enseignée par ce prof
        inscriptions = Inscription.objects.none()

    # Pour chaque inscription, on prépare les notes à afficher
    for ins in inscriptions:
        notes_etudiant = Note.objects.filter(inscription=ins)

        if matiere:
            notes_etudiant = notes_etudiant.filter(matiere=matiere)
        else:
            # Sans matière sélectionnée, on ignore pour ne pas surcharger
            continue

        # CC notes
        cc_notes = list(notes_etudiant.filter(type__in=cc_types).order_by("-date_eval")[:4])
        while len(cc_notes) < 4:
            cc_notes.append(None)

        # Examen
        exam_note = notes_etudiant.filter(type=examen_type).order_by("-date_eval").first()

        # Calcul moyenne pondérée
        total_coef = 0
        total_pondere = 0
        for note_obj in notes_etudiant:
            try:
                note_val = float(note_obj.note)
                pourcentage = note_obj.type.pourcentage
            except (ValueError, TypeError, AttributeError):
                continue
            total_pondere += note_val * pourcentage
            total_coef += pourcentage
        moyenne = total_pondere / total_coef if total_coef > 0 else 0.0

        notes_finales.append({
            "etudiant": ins.etudiant.utilisateur.get_full_name(),
            "classe": ins.classe.nom,
            "cc_notes": cc_notes,
            "exam_note": exam_note,
            "moyenne": round(moyenne, 2) if moyenne is not None else None,
            "inscription": ins,
            "matiere": matiere,
        })


    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response['Content-Disposition'] = 'attachment; filename="notes_etudiants.csv"'

        writer = csv.writer(response)
        writer.writerow(["Étudiant", "Classe", "CC1", "CC2", "CC3", "CC4", "Examen", "Moyenne"])

        for note in notes_finales:
            cc_notes = [cc.note if cc else "-" for cc in note["cc_notes"]]
            exam = note["exam_note"].note if note["exam_note"] else "-"
            row = [note["etudiant"], note["classe"]] + cc_notes + [exam, note["moyenne"]]
            writer.writerow(row)

        return response

    context = {
        "notes_finales": notes_finales,
        "matieres": matieres,
        "classes": classes,
        "annees": annees,
        "matiere_id": matiere_id,
        "classe_id": classe_id,
        "annee_id": annee_id,
        "recherche": recherche,
        "user": request.user,
    }
    return render(request, "core/prof_note_list.html", context)
    

@login_required
def add_notes_prof(request):
    if not request.user.is_prof:
        return redirect("logout")

    prof = request.user.prof
    matieres = prof.matieres.all()
    classes = Classe.objects.all()
    annees = AnneeScolaire.objects.all()
    cc_indices = range(1, 5)

    if request.method == "POST":
        matiere_id = request.POST.get("matiere")
        classe_id = request.POST.get("classe")
        annee_id = request.POST.get("annee")
        etudiant_id = request.POST.get("etudiant")

        # Validation simple des IDs
        if not (matiere_id and classe_id and annee_id and etudiant_id):
            messages.error(request, "Tous les champs sélectionnés sont obligatoires.")
            # On revient au formulaire avec erreurs
            context = {
                "matieres": matieres,
                "classes": classes,
                "annees": annees,
                "cc_indices": cc_indices,
                "request": request,
            }
            return render(request, "core/prof_add_note.html", context)

        matiere = get_object_or_404(Matiere, id=matiere_id)
        classe = get_object_or_404(Classe, id=classe_id)
        annee = get_object_or_404(AnneeScolaire, id=annee_id)
        etudiant = get_object_or_404(Etudiant, utilisateur__id=etudiant_id)

        inscription = Inscription.objects.filter(etudiant=etudiant, classe=classe, annee=annee).first()
        if not inscription:
            messages.error(request, "L'étudiant sélectionné n'est pas inscrit dans cette classe/année.")
            context = {
                "matieres": matieres,
                "classes": classes,
                "annees": annees,
                "cc_indices": cc_indices,
                "request": request,
            }
            return render(request, "core/prof_add_note.html", context)

        cc_types = Type.objects.filter(nom__icontains="Controle Continu")
        examen_type = Type.objects.filter(nom__icontains="Examen").first()
        if not examen_type:
            messages.error(request, "Type d'évaluation 'Examen' non défini.")
            context = {
                "matieres": matieres,
                "classes": classes,
                "annees": annees,
                "cc_indices": cc_indices,
                "request": request,
            }
            return render(request, "core/prof_add_note.html", context)

        # Sauvegarde des notes CC
        for i in cc_indices:
            note_val = request.POST.get(f"cc{i}")
            commentaire_val = request.POST.get(f"commentaire_cc{i}")
            date_val = parse_date_safe(request.POST.get(f"date_cc{i}"))
            cc_type = cc_types.first()  # à adapter si plusieurs types différents

            if note_val:
                Note.objects.update_or_create(
                    inscription=inscription,
                    matiere=matiere,
                    type=cc_type,
                    date_eval=date_val,
                    defaults={
                        "note": note_val,
                        "commentaire": commentaire_val,
                    },
                )
            else:
                Note.objects.filter(inscription=inscription, matiere=matiere, type=cc_type, date_eval=date_val).delete()

        # Note examen
        note_exam = request.POST.get("note_exam")
        commentaire_exam = request.POST.get("commentaire_exam")
        date_exam = parse_date_safe(request.POST.get("date_exam"))

        if note_exam:
            Note.objects.update_or_create(
                inscription=inscription,
                matiere=matiere,
                type=examen_type,
                date_eval=date_exam,
                defaults={
                    "note": note_exam,
                    "commentaire": commentaire_exam,
                },
            )
        else:
            Note.objects.filter(inscription=inscription, matiere=matiere, type=examen_type, date_eval=date_exam).delete()

        messages.success(request, "Notes enregistrées avec succès !")
        return redirect("prof_note_list")

    # Si GET ou autre méthode, afficher le formulaire
    context = {
        "matieres": matieres,
        "classes": classes,
        "annees": annees,
        "cc_indices": cc_indices,
        "request": request,
    }
    return render(request, "core/prof_add_note.html", context)


@login_required
def edit_notes_prof(request,inscription_id, matiere_id):
    if not request.user.is_authenticated or not request.user.is_prof:
        return redirect("logout")
    
    inscription = get_object_or_404(Inscription, id=inscription_id)    

    prof = request.user.prof

    # Récupérer les matières enseignées par ce prof dans cette classe/année (optionnel)
    matieres = prof.matieres.all()

    # Récupérer matière sélectionnée dans le formulaire
    matiere = get_object_or_404(Matiere, id=matiere_id)
    
    cc_types = Type.objects.filter(nom__icontains="Controle")  # ou "Contrôle"
    exam_type = Type.objects.filter(nom__icontains="Examen").first()

    # Notes existantes par type (id) -> liste de notes
    notes = Note.objects.filter(inscription=inscription)
    notes_par_type = defaultdict(list)
    for n in notes:
        notes_par_type[n.type.id].append(n)

    if request.method == "POST":
        # Traitement POST: on récupère les données et on met à jour ou crée les notes


        # Securité : vérifier que la matière appartient au prof
        if matiere not in matieres:
            return HttpResponseForbidden("Matière non autorisée")
        
        # Contrôles continus
        for cc_type in cc_types:
            for i in range(1, 5):  # jusqu'à 4 CC par type
                note_val = request.POST.get(f"cc{cc_type.id}_{i}")
                commentaire = request.POST.get(f"commentaire_cc{cc_type.id}_{i}", "")
                date_eval = parse_date_safe(request.POST.get(f"date_cc{cc_type.id}_{i}"))
                if note_val or commentaire or date_eval:
                    # Soit on met à jour une note existante, soit on crée une nouvelle
                    # On essaie de récupérer une note existante à cet index
                    try:
                        note_obj = notes_par_type[cc_type.id][i-1]
                        # Mise à jour
                        note_obj.note = note_val if note_val else ""
                        note_obj.commentaire = commentaire
                        if date_eval:
                            note_obj.date_eval = date_eval

                        note_obj.save()
                    except IndexError:
                        # Pas de note existante, création
                        if note_val:  # on crée uniquement si note
                            Note.objects.create(
                                inscription=inscription,
                                matiere=matiere,  # ou la matière spécifique si connue
                                type=cc_type,
                                note=note_val,
                                commentaire=commentaire,
                                date_eval=date_eval or None,
                            )

        # Examen (un seul)
        if exam_type:
            note_exam = request.POST.get("note_exam")
            commentaire_exam = request.POST.get("commentaire_exam", "")
            date_exam = parse_date_safe(request.POST.get("date_exam"))
            if note_exam or commentaire_exam or date_exam:
                # Si note examen existe déjà, on la modifie
                exam_notes = notes_par_type.get(exam_type.id, [])
                if exam_notes:
                    note_obj = exam_notes[0]
                    note_obj.note = note_exam if note_exam else ""
                    note_obj.commentaire = commentaire_exam
                    if date_exam:
                        note_obj.date_eval = date_exam
                    note_obj.save()
                else:
                    # Création nouvelle note examen
                    if note_exam:
                        Note.objects.create(
                            inscription=inscription,
                            matiere= matiere,
                            type=exam_type,
                            note=note_exam,
                            commentaire=commentaire_exam,
                            date_eval=date_exam or None,
                        )

        # Après sauvegarde, rediriger (vers liste, ou même page pour confirmation)
        messages.success(request, "✅ Notes modifiées avec succès.")
        return redirect("prof_note_list")
    
    context = {
        "inscription": inscription,
        "matiere": matiere,
        "cc_types": cc_types,
        "exam_type": exam_type,
        "notes_par_type": notes_par_type,
    }
    return render(request, "core/prof_edit_note.html", context)


@login_required
def note_etudiant(request):
    if not request.user.is_etudiant:
        return redirect("logout")

    etudiant = request.user.etudiant

    matiere_id = request.GET.get("matiere")
    classe_id = request.GET.get("classe")
    annee_id = request.GET.get("annee")

    inscriptions = Inscription.objects.filter(etudiant=etudiant)

    # 🔹 Données pour les filtres : indépendantes
    classes = Classe.objects.filter(id__in=inscriptions.values_list("classe_id", flat=True)).distinct()
    matieres = Matiere.objects.filter(id__in=Note.objects.filter(inscription__in=inscriptions).values_list("matiere_id", flat=True)).distinct()
    annees = AnneeScolaire.objects.filter(id__in=inscriptions.values_list("annee_id", flat=True)).distinct().order_by("nom")


    # 🔹 Si aucune année précisée, prendre la première par défaut
    if not annee_id and annees.exists():
        annee_id = str(annees.first().id)

    if annee_id:
        inscriptions = inscriptions.filter(annee_id=annee_id)
    if classe_id:
        inscriptions = inscriptions.filter(classe_id=classe_id)

    if matiere_id:
        try:
            matiere = Matiere.objects.get(id=matiere_id)
        except Matiere.DoesNotExist:
            matiere = None
            inscriptions = Inscription.objects.none()
        else:
            inscriptions = inscriptions.filter(note__matiere=matiere).distinct()
    else:
        matiere = None

    cc_types = Type.objects.filter(nom__icontains="Controle Continu")
    examen_type = Type.objects.filter(nom__icontains="Examen").first()

    notes_finales = []

    for ins in inscriptions:
    # Récupérer toutes les notes de cette inscription (sans filtre matière)
        notes_etudiant = Note.objects.filter(inscription=ins)

        # Regrouper les notes par matière
        matieres_notes = {}
        for note_obj in notes_etudiant:
            mat = note_obj.matiere
            if mat not in matieres_notes:
                matieres_notes[mat] = []
            matieres_notes[mat].append(note_obj)

        # Pour chaque matière, préparer la ligne de notes
        for mat, notes_mat in matieres_notes.items():
            # CC notes
            cc_notes = [n for n in notes_mat if "Controle Continu" in n.type.nom]
            cc_notes = sorted(cc_notes, key=lambda n: n.date_eval, reverse=True)[:4]
            while len(cc_notes) < 4:
                cc_notes.append(None)

            # Examen
            exam_note = next((n for n in notes_mat if "Examen" in n.type.nom), None)

            # Calcul moyenne pondérée pour cette matière
            total_coef = 0
            total_pondere = 0
            for note_obj in notes_mat:
                try:
                    note_val = float(note_obj.note)
                    pourcentage = note_obj.type.pourcentage
                except (ValueError, TypeError, AttributeError):
                    continue
                total_pondere += note_val * pourcentage
                total_coef += pourcentage
            moyenne = total_pondere / total_coef if total_coef > 0 else 0.0

            notes_finales.append({
                "etudiant": ins.etudiant.utilisateur.get_full_name(),
                "classe": ins.classe.nom,
                "cc_notes": cc_notes,
                "exam_note": exam_note,
                "moyenne": round(moyenne, 2) if moyenne is not None else None,
                "inscription": ins,
                "matiere": mat,
            })

    context = {
        "matieres": matieres,
        "classes": classes,
        "annees": annees,
        "matiere_id": matiere_id,
        "classe_id": classe_id,
        "annee_id": annee_id,
        "notes_finales": notes_finales,
        "user": request.user,
    }

    return render(request, "core/etudiant_note.html", context)

    
@login_required
def bulletin_etudiant(request):
    if not request.user.is_etudiant:
        return redirect("logout")

    etudiant = request.user.etudiant

    # Récupérer les filtres
    annee_id = request.GET.get("annee")
    classe_id = request.GET.get("classe")

    # Filtrer les inscriptions de cet étudiant
    inscriptions = Inscription.objects.filter(etudiant=etudiant)

    # Pour les filtres disponibles, on limite les sélections possibles aux inscriptions
    annees = AnneeScolaire.objects.filter(id__in=inscriptions.values_list("annee_id", flat=True)).distinct()
    classes = Classe.objects.filter(id__in=inscriptions.values_list("classe_id", flat=True)).distinct()

    # Si aucune année choisie, prendre la première dispo
    if not annee_id and annees.exists():
        annee_id = annees.first().id

    if annee_id:
        inscriptions = inscriptions.filter(annee_id=annee_id)
    if classe_id:
        inscriptions = inscriptions.filter(classe_id=classe_id)

    # On récupère toutes les notes liées aux inscriptions filtrées
    notes = Note.objects.filter(inscription__in=inscriptions)

    # Regrouper les notes par matière pour faire la moyenne matière
    matieres = {}
    for note_obj in notes:
        mat = note_obj.matiere
        if mat not in matieres:
            matieres[mat] = {
                "notes": [],
                "coef_total": 0,
                "pondere_total": 0,
            }
        try:
            note_val = float(note_obj.note)
            pourcentage = note_obj.type.pourcentage
        except (ValueError, TypeError, AttributeError):
            continue
        matieres[mat]["notes"].append(note_val)
        matieres[mat]["coef_total"] += pourcentage
        matieres[mat]["pondere_total"] += note_val * pourcentage

    # Préparer la liste à passer au template : matière + moyenne
    liste_moyennes = []
    total_pondere = 0
    total_coef = 0
    for mat, data in matieres.items():
        if data["coef_total"] > 0:
            moyenne_mat = data["pondere_total"] / data["coef_total"]
        else:
            moyenne_mat = 0
        liste_moyennes.append({
            "matiere": mat.nom,
            "moyenne": round(moyenne_mat, 2)
        })
        total_pondere += data["pondere_total"]
        total_coef += data["coef_total"]

    moyenne_generale = round(total_pondere / total_coef, 2) if total_coef > 0 else None

    context = {
        "annees": annees,
        "classes": classes,
        "annee_id": int(annee_id) if annee_id else None,
        "classe_id": int(classe_id) if classe_id else None,
        "liste_moyennes": liste_moyennes,
        "moyenne_generale": moyenne_generale,
        "user": request.user,
    }

    return render(request, "core/etudiant_bulletin.html", context)

@login_required
def releve_pdf(request, annee_id, classe_id):
    if not request.user.is_etudiant:
        return redirect("logout")

    etudiant = request.user.etudiant

    # Récupération des filtres (année et classe)
    #annee_id = request.GET.get("annee")
    #classe_id = request.GET.get("classe")

    inscriptions = Inscription.objects.filter(etudiant=etudiant)

    if annee_id:
        inscriptions = inscriptions.filter(annee_id=annee_id)
    if classe_id:
        inscriptions = inscriptions.filter(classe_id=classe_id)

    inscription = inscriptions.first()
    if not inscription:
        return HttpResponse("Aucune inscription trouvée pour ces filtres.", status=404)

    notes = Note.objects.filter(inscription=inscription)

    # Calcul moyennes par matière
    liste_moyennes = []
    matieres = Matiere.objects.filter(note__in=notes).distinct()

    for matiere in matieres:
        notes_matiere = notes.filter(matiere=matiere)
        total_pondere = 0
        total_coef = 0
        for note in notes_matiere:
            try:
                note_val = float(note.note)
                coef = note.type.pourcentage
                total_pondere += note_val * coef
                total_coef += coef
            except Exception:
                continue
        moyenne = total_pondere / total_coef if total_coef > 0 else 0.0
        liste_moyennes.append({
            "matiere": matiere.nom,
            "moyenne": round(moyenne, 2),
        })

    moyenne_generale = round(sum(item["moyenne"] for item in liste_moyennes) / len(liste_moyennes), 2) if liste_moyennes else 0.0

    context = {
        "etudiant": etudiant.utilisateur.get_full_name(),
        "annee": inscription.annee.nom,
        "classe": inscription.classe.nom,
        "liste_moyennes": liste_moyennes,
        "moyenne_generale": moyenne_generale,
    }

    # Render HTML with context
    html_string = render_to_string("core/etudiant_releve_pdf.html", context)

    # Generate PDF
    html = HTML(string=html_string)
    pdf_file = html.write_pdf()

    response = HttpResponse(pdf_file, content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename="bulletin_{etudiant.utilisateur.username}.pdf"'
    return response

@login_required
def get_etudiants_ajax(request):
    classe_id = request.GET.get("classe_id")
    annee_id = request.GET.get("annee_id")

    if not (classe_id and annee_id):
        return JsonResponse({"etudiants": []})

    inscriptions = Inscription.objects.filter(
        classe_id=classe_id,
        annee_id=annee_id
    ).select_related("etudiant__utilisateur")

    etudiants = [
        {"id": ins.etudiant.utilisateur.id, "nom": ins.etudiant.utilisateur.get_full_name()}
        for ins in inscriptions
    ]
    return JsonResponse({"etudiants": etudiants})  # 