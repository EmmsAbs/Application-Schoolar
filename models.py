from django.contrib.auth.models import AbstractUser
from django.db import models

class Utilisateur(AbstractUser):
    adresse = models.CharField(max_length=255)
    email = models.EmailField(unique=True)


    @property
    def is_etudiant(self):
        return hasattr(self, 'etudiant')

    @property
    def is_prof(self):
        return hasattr(self, 'prof')

    @property
    def is_gestionnaire(self):
        return hasattr(self, 'gestionnaire')

class Prof(models.Model):
    utilisateur = models.OneToOneField(Utilisateur, on_delete=models.CASCADE)
    actif = models.BooleanField(default=True)

class Gestionnaire(models.Model):
    utilisateur = models.OneToOneField(Utilisateur, on_delete=models.CASCADE)
    actif = models.BooleanField(default=True)
    
    def save(self, *args, **kwargs):
        # Activer le droit d'accès à l'admin
        self.utilisateur.is_staff = True
        self.utilisateur.save()
        super().save(*args, **kwargs)

class Etudiant(models.Model):
    utilisateur = models.OneToOneField(Utilisateur, on_delete=models.CASCADE)
    actif = models.BooleanField(default=True)
    dateCrea = models.DateTimeField(auto_now_add=True)

class Classe(models.Model):
    nom = models.CharField(max_length=255)

class Matiere(models.Model):
    nom = models.CharField(max_length=255)
    coefficient = models.IntegerField()
    profs = models.ManyToManyField(Prof, related_name="matieres")
    dateCreat = models.DateTimeField(auto_now_add=True)

class AnneeScolaire(models.Model):
    nom = models.CharField(max_length=255)

class Inscription(models.Model):
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE)
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE)
    annee = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE)
    date_inscription = models.DateTimeField(auto_now_add=True)

class Type(models.Model):
    nom = models.CharField(max_length=255)
    pourcentage = models.IntegerField()

class Note(models.Model):
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE)
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    type = models.ForeignKey(Type, on_delete=models.CASCADE)
    note = models.CharField(max_length=10)
    commentaire = models.TextField(blank=True, null=True)
    date_eval = models.DateTimeField(blank=True, null=True)
    date_crea = models.DateTimeField(auto_now_add=True)

class Bulletin(models.Model):
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE)
    moyenne = models.FloatField()
    rang = models.IntegerField()
    date_gene = models.DateTimeField(auto_now_add=True)
