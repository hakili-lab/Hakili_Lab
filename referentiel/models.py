"""
Le référentiel et la banque de questions — importés du classeur, jamais saisis.

Source unique : `Referentiel_Socle_v0.xlsx`, chargé par
`python manage.py importer_referentiel`. Toute correction se fait dans le
classeur puis par réimport, jamais directement en base : sinon la base et le
classeur divergent et plus personne ne sait lequel fait foi.

Règle de codage à ne jamais transgresser (guide-v2.md) : les codes locaux des
matrices de test (`N-a`, `G-c`…) sont **locaux à un test** — `N-a` désigne 7
compétences différentes selon le niveau, vérifié au module 0. Ils ne sont donc
jamais une clé : `Question.code_local` les conserve pour la traçabilité, mais
c'est `Question.competence` qui porte le sens.
"""
from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Domaine(models.TextChoices):
    """Les 8 domaines de l'onglet 02_Competences, tels qu'écrits dans le classeur.

    Libellés sans accents parce que c'est la graphie de la source : les valeurs
    servent de clé de rapprochement à l'import. Les accents du classeur font
    l'objet d'une correction à part (docs/accents_a_corriger.md).
    """

    NUMERIQUE = "Activites numeriques", "Activités numériques"
    ALGEBRE = "Calcul litteral et algebre", "Calcul littéral et algèbre"
    GEOMETRIE = "Activites geometriques", "Activités géométriques"
    MESURES = "Mesures et grandeurs", "Mesures et grandeurs"
    FONCTIONS = "Fonctions et applications", "Fonctions et applications"
    DONNEES = "Donnees, proportionnalite, statistique", "Données, proportionnalité, statistique"
    SUITES = "Suites et raisonnement", "Suites et raisonnement"
    TRIGONOMETRIE = "Trigonometrie", "Trigonométrie"


class NiveauTest(models.TextChoices):
    """Les 7 tests d'entrée. Valeurs = graphie du classeur (colonne « Niveau du test »)."""

    SIXIEME = "6eme", "6ème"
    CINQUIEME = "5eme", "5ème"
    QUATRIEME = "4eme", "4ème"
    TROISIEME = "3eme", "3ème"
    SECONDE_C = "2ndeC", "2nde C"
    PREMIERE_D = "1ereD", "1ère D"
    TERMINALE_D = "tleD", "Terminale D"


class FormatQuestion(models.TextChoices):
    """Quatre formats, pas trois.

    `guide-v2.md` (module 2) n'en décrit que trois — le format `construction`
    (7 questions, toutes en partie B) a été trouvé au module 0. Il attend un tracé
    géométrique et non du texte : son diagnostic automatique n'est vraisemblablement
    pas atteignable, il relèvera de la saisie humaine.
    """

    QCM = "qcm", "QCM"
    COURT = "court", "Réponse courte"
    REDIGE = "redige", "Exercice rédigé"
    CONSTRUCTION = "construction", "Construction géométrique"


class Partie(models.TextChoices):
    A = "A", "Partie A — questions courtes"
    B = "B", "Partie B — exercices rédigés"


class TypeErreur(models.Model):
    """Les 7 types d'erreur. Liste FERMÉE — n'en jamais ajouter un huitième
    sans décision explicite (protocole-v2.md §3).

    `ATT` (inattention) existe pour être **écarté** : son coefficient est 0 et il
    ne donne jamais lieu à remédiation. Conséquence à connaître pour le module 6 :
    `CoutRemediation` ne contient aucune ligne `ATT` par construction. Un accès
    naïf lèverait une erreur sur un cas parfaitement normal — traiter `ATT` comme
    coût 0.
    """

    code = models.CharField(max_length=3, primary_key=True)
    libelle = models.CharField("libellé", max_length=100)
    definition = models.TextField("définition")
    signature = models.TextField("signature observable sur la copie")
    exemple = models.TextField("exemple concret", blank=True)
    coefficient = models.DecimalField(
        "coefficient de coût",
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    remediable = models.BooleanField("donne lieu à remédiation")

    class Meta:
        verbose_name = "type d'erreur"
        verbose_name_plural = "types d'erreur"
        ordering = ["-coefficient", "code"]

    def __str__(self) -> str:
        return f"{self.code} — {self.libelle}"


class Competence(models.Model):
    """Les 101 compétences canoniques, du primaire à la Terminale D.

    Le volume horaire est officiel pour les 74 compétences du collège. Pour les 27
    du lycée, les documents du secondaire ne donnent qu'une progression mensuelle,
    sans volume par chapitre : une **valeur de repli** est appliquée et signalée par
    `volume_estime` (voir `referentiel/couts.py` pour le choix de cette valeur et
    ce qu'il évite). Sans elle, le palier A/B/C d'un élève de 2nde ou de 1ère
    resterait indéterminable.
    """

    code = models.CharField("code canonique", max_length=20, primary_key=True)
    domaine = models.CharField(max_length=60, choices=Domaine.choices)
    libelle = models.CharField("libellé", max_length=200)
    description = models.TextField(blank=True)
    niveau_intro = models.CharField("niveau d'introduction", max_length=20)
    chapitre_intro = models.CharField("chapitre d'origine", max_length=100, blank=True)
    transversale = models.BooleanField(default=False)
    volume_horaire = models.DecimalField(
        "volume horaire (h)",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Officiel pour le collège. Valeur de repli pour le lycée, où les "
        "documents ne donnent pas de volume par chapitre — `volume_estime` le signale.",
    )
    source_volume = models.CharField(max_length=120, blank=True)
    volume_estime = models.BooleanField(
        "volume estimé",
        default=False,
        help_text="Vrai quand le volume est une valeur de repli et non un chiffre "
        "officiel — le cas des 27 compétences de lycée. Voir referentiel/couts.py.",
    )

    class Meta:
        verbose_name = "compétence"
        ordering = ["domaine", "code"]
        indexes = [models.Index(fields=["domaine"]), models.Index(fields=["niveau_intro"])]

    def __str__(self) -> str:
        return f"{self.code} — {self.libelle}"


class Prerequis(models.Model):
    """Graphe des prérequis directs.

    C'est ce qui permet de remonter d'un échec vers la lacune ancienne qui
    l'explique, au lieu de soigner le symptôme — et c'est ce graphe que le module 6
    parcourt pour ordonner le plan de remédiation (un problème dont un prérequis
    est aussi en difficulté se traite après lui, jamais avant).
    """

    competence = models.ForeignKey(
        Competence, on_delete=models.CASCADE, related_name="prerequis"
    )
    prerequis = models.ForeignKey(
        Competence, on_delete=models.CASCADE, related_name="requis_par"
    )

    class Meta:
        verbose_name = "prérequis"
        verbose_name_plural = "prérequis"
        constraints = [
            models.UniqueConstraint(
                fields=["competence", "prerequis"], name="prerequis_unique"
            ),
            # Une compétence prérequis d'elle-même créerait une boucle infinie
            # au parcours du graphe (module 6).
            models.CheckConstraint(
                condition=~models.Q(competence=models.F("prerequis")),
                name="prerequis_pas_reflexif",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.competence_id} ← {self.prerequis_id}"


class CoutRemediation(models.Model):
    """Coût horaire précalculé pour chaque couple compétence × type d'erreur.

    coût = volume horaire officiel × coefficient du type d'erreur, arrondi à
    **l'heure entière supérieure**, plancher 1 h, plafond 4 h. Le plafond évite
    qu'un seul problème absorbe la moitié d'un plan ; l'arrondi vers le haut
    évite d'inscrire un volume qu'on sait insuffisant (décision du 2026-08-01).

    606 lignes = 101 compétences × 6 types remédiables. `ATT` n'y figure jamais :
    non remédiable, coefficient 0 — l'absence d'une ligne `ATT` est normale, pas
    une anomalie, et le module 6 doit la traiter comme un coût nul.

    Les 162 lignes des 27 compétences de lycée dérivent d'un **volume de repli**
    (voir referentiel/couts.py) et portent `estime = True`. Sans elles, le palier
    d'un élève de 2nde ou de 1ère resterait indéterminable.
    """

    competence = models.ForeignKey(
        Competence, on_delete=models.CASCADE, related_name="couts"
    )
    type_erreur = models.ForeignKey(
        TypeErreur, on_delete=models.CASCADE, related_name="couts"
    )
    cout_heures = models.DecimalField(
        "coût estimé (h)",
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(0.5), MaxValueValidator(4)],
    )
    derivation = models.CharField(
        "dérivation du volume", max_length=200, blank=True,
        help_text="Trace du calcul, reprise du classeur — ex. « 4e ch15 : 4 h / 2 = 2.0 h ».",
    )
    estime = models.BooleanField(
        "coût estimé",
        default=False,
        help_text="Vrai quand le coût dérive d'un volume de repli et non d'un volume "
        "officiel. À afficher comme tel : ce n'est pas une valeur du curriculum.",
    )

    class Meta:
        verbose_name = "coût de remédiation"
        verbose_name_plural = "coûts de remédiation"
        ordering = ["competence", "-cout_heures"]
        constraints = [
            models.UniqueConstraint(
                fields=["competence", "type_erreur"], name="cout_unique_par_couple"
            )
        ]

    def __str__(self) -> str:
        return f"{self.competence_id} × {self.type_erreur_id} = {self.cout_heures} h"


class Question(models.Model):
    """Les 280 questions des 7 tests d'entrée — 40 par test.

    `bareme` est stocké **sur 20** (décision D-CEO-26) : le classeur note sur 60
    (30 questions de partie A à 1 pt, 10 exercices de partie B à 3 pts), converti
    par 3 à l'import. `bareme_classeur` conserve la valeur d'origine, entière et
    donc exacte, pour la traçabilité.

    Une question de partie A vaut 1/3 de point, non représentable exactement en
    décimal (30 × 0,333333 = 9,99999). **La note doit toujours se calculer contre
    la somme réelle des barèmes, jamais contre un total déclaré** — sinon une copie
    parfaite ne vaut pas 20/20, comme c'était le cas sur les anciens barèmes.

    `reponse_attendue` et `solution` sont vides pour 209 des 280 questions : le
    classeur ne donne la bonne réponse que pour les 71 QCM. Les colonnes existent
    dès la première version pour que remplir les corrigés (arbitrage B de
    docs/harmonisation_donnees.md) n'impose pas de migration.
    """

    code_question = models.CharField(max_length=10)
    niveau_test = models.CharField(max_length=10, choices=NiveauTest.choices)
    partie = models.CharField(max_length=1, choices=Partie.choices)
    format = models.CharField(max_length=15, choices=FormatQuestion.choices)
    bareme = models.DecimalField("barème (sur 20)", max_digits=8, decimal_places=6)
    bareme_classeur = models.DecimalField(
        "barème d'origine (sur 60)", max_digits=4, decimal_places=1
    )
    code_local = models.CharField(
        max_length=10,
        blank=True,
        help_text="Code de la matrice du test — LOCAL à ce test, jamais une clé.",
    )
    competence = models.ForeignKey(
        Competence, on_delete=models.PROTECT, related_name="questions"
    )
    competence_secondaire = models.ForeignKey(
        Competence,
        on_delete=models.PROTECT,
        related_name="questions_secondaires",
        null=True,
        blank=True,
    )
    objet = models.TextField("objet de la question")
    reponse_attendue = models.TextField(
        "réponse attendue",
        blank=True,
        help_text="Lettre de l'option pour un QCM. Vide pour les 209 questions "
        "sans corrigé au classeur (arbitrage B).",
    )
    solution = models.TextField("démarche attendue", blank=True)

    class Meta:
        verbose_name = "question"
        ordering = ["niveau_test", "partie", "code_question"]
        constraints = [
            models.UniqueConstraint(
                fields=["niveau_test", "code_question"], name="question_unique_par_test"
            )
        ]
        indexes = [
            models.Index(fields=["niveau_test", "partie"]),
            models.Index(fields=["competence"]),
        ]

    def __str__(self) -> str:
        return f"{self.niveau_test}/{self.code_question}"

    @property
    def a_corrige(self) -> bool:
        return bool(self.reponse_attendue)


class SignatureErreur(models.Model):
    """Les 1031 signatures : ce qu'on lit concrètement sur la copie, et la lacune
    que cela révèle. 3 à 4 par question, les 280 questions couvertes.

    C'est la matière du module 4 : le modèle ne devine pas un type d'erreur, il
    **reconnaît** une signature parmi celles de la question concernée.
    """

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="signatures"
    )
    competence = models.ForeignKey(
        Competence, on_delete=models.PROTECT, related_name="signatures"
    )
    type_erreur = models.ForeignKey(
        TypeErreur, on_delete=models.PROTECT, related_name="signatures"
    )
    production_eleve = models.TextField("ce qu'on lit sur la copie")
    interpretation = models.TextField("lacune révélée")

    class Meta:
        verbose_name = "signature d'erreur"
        verbose_name_plural = "signatures d'erreur"
        ordering = ["question", "type_erreur"]
        indexes = [models.Index(fields=["type_erreur"])]

    def __str__(self) -> str:
        return f"{self.question} [{self.type_erreur_id}]"


class OptionQcm(models.Model):
    """Les 284 options de QCM, chaque mauvaise réponse taguée par le type d'erreur
    qui conduit à la choisir.

    C'est ce qui rend le diagnostic d'un QCM entièrement mécanique : une lettre
    cochée donne directement un problème. **Aucun appel de modèle de langage ne
    doit avoir lieu pour interpréter un QCM** (guide-v2.md, module 4).
    """

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="options"
    )
    lettre = models.CharField(max_length=2)
    texte = models.TextField()
    correcte = models.BooleanField(default=False)
    type_erreur = models.ForeignKey(
        TypeErreur,
        on_delete=models.PROTECT,
        related_name="options",
        null=True,
        blank=True,
        help_text="Nul pour la bonne réponse : elle ne révèle aucune erreur.",
    )
    erreur = models.TextField(
        "erreur qui conduit à cette option", blank=True
    )

    class Meta:
        verbose_name = "option de QCM"
        verbose_name_plural = "options de QCM"
        ordering = ["question", "lettre"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "lettre"], name="option_unique_par_question"
            ),
            # Une bonne réponse ne révèle pas d'erreur, une mauvaise en révèle une.
            # Contrainte en base plutôt qu'en convention : c'est cet invariant qui
            # autorise le module 4 à conclure sans interprétation.
            models.CheckConstraint(
                condition=(
                    models.Q(correcte=True, type_erreur__isnull=True)
                    | models.Q(correcte=False, type_erreur__isnull=False)
                ),
                name="option_type_erreur_coherent",
            ),
        ]

    def __str__(self) -> str:
        marque = " ✓" if self.correcte else ""
        return f"{self.question} {self.lettre}){marque}"
