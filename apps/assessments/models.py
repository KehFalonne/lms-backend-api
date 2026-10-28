import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ──────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────
class QuestionType(models.TextChoices):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE", _("Multiple choice")
    MULTIPLE_ANSWER = "MULTIPLE_ANSWER", _("Multiple answer")
    TRUE_FALSE = "TRUE_FALSE", _("True / False")
    SHORT_ANSWER = "SHORT_ANSWER", _("Short answer")
    LONG_ANSWER = "LONG_ANSWER", _("Essay / long answer")
    NUMERIC = "NUMERIC", _("Numeric")
    MATCHING = "MATCHING", _("Matching")
    FILL_BLANK = "FILL_BLANK", _("Fill in the blank")


class QuestionDifficulty(models.TextChoices):
    EASY = "EASY", _("Easy")
    MEDIUM = "MEDIUM", _("Medium")
    HARD = "HARD", _("Hard")


class QuestionStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Draft")
    PUBLISHED = "PUBLISHED", _("Published")
    ARCHIVED = "ARCHIVED", _("Archived")


class BankVisibility(models.TextChoices):
    PRIVATE = "PRIVATE", _("Private")
    DEPARTMENT = "DEPARTMENT", _("Department")
    INSTITUTION = "INSTITUTION", _("Institution")


class AssessmentType(models.TextChoices):
    QUIZ = "QUIZ", _("Quiz")
    TEST = "TEST", _("Test")
    MIDTERM = "MIDTERM", _("Midterm")
    FINAL_EXAM = "FINAL_EXAM", _("Final exam")
    PRACTICE = "PRACTICE", _("Practice")


class AssessmentStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Draft")
    PUBLISHED = "PUBLISHED", _("Published")
    CLOSED = "CLOSED", _("Closed")
    ARCHIVED = "ARCHIVED", _("Archived")


class AttemptStatus(models.TextChoices):
    IN_PROGRESS = "IN_PROGRESS", _("In progress")
    SUBMITTED = "SUBMITTED", _("Submitted")
    AUTO_GRADED = "AUTO_GRADED", _("Auto-graded")
    MANUAL_GRADING = "MANUAL_GRADING", _("Pending manual grading")
    GRADED = "GRADED", _("Graded")
    EXPIRED = "EXPIRED", _("Expired")
    INVALIDATED = "INVALIDATED", _("Invalidated")


# ──────────────────────────────────────────────────────────────────────
# Question Bank (database doc §17)
# ──────────────────────────────────────────────────────────────────────
class QuestionBank(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="question_banks",
    )
    department = models.ForeignKey(
        "university.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="question_banks",
    )

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="owned_question_banks",
    )
    visibility = models.CharField(
        _("visibility"),
        max_length=20,
        choices=BankVisibility.choices,
        default=BankVisibility.PRIVATE,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("question bank")
        verbose_name_plural = _("question banks")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


# ──────────────────────────────────────────────────────────────────────
# Question
# ──────────────────────────────────────────────────────────────────────
class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    question_bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.CASCADE,
        related_name="questions",
    )

    question_type = models.CharField(
        _("type"),
        max_length=30,
        choices=QuestionType.choices,
        db_index=True,
    )
    text = models.TextField(_("text"))
    explanation = models.TextField(_("explanation"), blank=True)

    difficulty = models.CharField(
        _("difficulty"),
        max_length=10,
        choices=QuestionDifficulty.choices,
        default=QuestionDifficulty.MEDIUM,
    )
    default_points = models.DecimalField(
        _("points"),
        max_digits=6,
        decimal_places=2,
        default=1,
    )

    tags = models.JSONField(_("tags"), default=list, blank=True)

    # Type-specific payloads — nullable, only one will be filled based on type.
    answer_key = models.JSONField(
        _("answer key"),
        default=list,
        blank=True,
        help_text=_("Accepted strings for SHORT_ANSWER / FILL_BLANK."),
    )
    numeric_answer = models.DecimalField(
        _("numeric answer"),
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    numeric_tolerance = models.DecimalField(
        _("numeric tolerance"),
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    matching_pairs = models.JSONField(
        _("matching pairs"),
        default=list,
        blank=True,
        help_text=_("[{left, right}, ...] for MATCHING."),
    )
    sample_answer = models.TextField(
        _("sample answer"),
        blank=True,
        help_text=_("Grading guide for LONG_ANSWER."),
    )
    blank_count = models.PositiveSmallIntegerField(
        _("blank count"),
        null=True,
        blank=True,
    )

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=QuestionStatus.choices,
        default=QuestionStatus.DRAFT,
        db_index=True,
    )
    current_version = models.PositiveIntegerField(_("current version"), default=1)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="questions_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    class Meta:
        verbose_name = _("question")
        verbose_name_plural = _("questions")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["question_bank", "status"]),
            models.Index(fields=["question_type"]),
            models.Index(fields=["difficulty"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_question_type_display()} — {self.text[:60]}"

    def clean(self):
        # Only check when the question is being marked ready (not for auto-graded drafts)
        if self.question_type == QuestionType.NUMERIC and self.numeric_answer is None:
            raise ValidationError(
                {"numeric_answer": _("Required for numeric questions.")}
            )


class QuestionOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options",
    )
    text = models.CharField(_("text"), max_length=500)
    is_correct = models.BooleanField(_("correct"), default=False)
    position = models.PositiveSmallIntegerField(_("position"), default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("question option")
        verbose_name_plural = _("question options")
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "position"],
                name="uniq_question_option_position",
            ),
        ]


class QuestionVersion(models.Model):
    """Immutable snapshot of a question (database doc §37)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version = models.PositiveIntegerField()
    snapshot = models.JSONField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = _("question version")
        verbose_name_plural = _("question versions")
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "version"],
                name="uniq_question_version",
            ),
        ]


# ──────────────────────────────────────────────────────────────────────
# Assessment (database doc §18)
# ──────────────────────────────────────────────────────────────────────
class Assessment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course_offering = models.ForeignKey(
        "courses.CourseOffering",
        on_delete=models.CASCADE,
        related_name="assessments",
    )

    title = models.CharField(_("title"), max_length=250)
    description = models.TextField(_("description"), blank=True)
    instructions = models.TextField(_("instructions"), blank=True)

    assessment_type = models.CharField(
        _("type"),
        max_length=20,
        choices=AssessmentType.choices,
        default=AssessmentType.QUIZ,
    )

    total_points = models.DecimalField(
        _("total points"),
        max_digits=8,
        decimal_places=2,
        default=0,
    )

    available_from = models.DateTimeField(_("available from"), null=True, blank=True)
    available_until = models.DateTimeField(_("available until"), null=True, blank=True)
    # ── CA workflow (backend doc §4.3.1) ──────────────────────────
    is_code_gated = models.BooleanField(
        _("code-gated"),
        default=False,
        help_text=_("Require an access code to enter this assessment."),
    )
    access_code_hash = models.CharField(
        _("access code hash"),
        max_length=255,
        blank=True,
        help_text=_("Hashed access code — never store the raw code."),
    )
    ca_opens_at = models.DateTimeField(
        _("opens at"),
        null=True,
        blank=True,
        help_text=_("Earliest entry time. Students cannot enter before this."),
    )
    ca_last_entry_at = models.DateTimeField(
        _("last entry at"),
        null=True,
        blank=True,
        help_text=_("Latest time a student can enter the attempt window."),
    )
    serve_question_count = models.PositiveIntegerField(
        _("questions to serve"),
        null=True,
        blank=True,
        help_text=_(
            "If set and less than the total, each student gets a random subset."
        ),
    )
    randomize_question_order = models.BooleanField(
        _("randomize question order"),
        default=False,
    )
    time_limit_minutes = models.PositiveIntegerField(
        _("time limit (min)"), null=True, blank=True
    )

    max_attempts = models.PositiveSmallIntegerField(_("max attempts"), default=1)

    shuffle_questions = models.BooleanField(default=False)
    shuffle_options = models.BooleanField(default=False)

    show_results = models.BooleanField(_("show results"), default=True)
    show_correct_answers = models.BooleanField(_("show correct answers"), default=False)

    passing_score = models.DecimalField(
        _("passing score"),
        max_digits=6,
        decimal_places=2,
        default=50,
    )

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=AssessmentStatus.choices,
        default=AssessmentStatus.DRAFT,
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="assessments_created",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("assessment")
        verbose_name_plural = _("assessments")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["course_offering", "status"]),
            models.Index(fields=["available_from"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.assessment_type})"

    @property
    def is_open(self) -> bool:
        if self.status != AssessmentStatus.PUBLISHED:
            return False
        now = timezone.now()
        if self.available_from and now < self.available_from:
            return False
        if self.available_until and now > self.available_until:
            return False
        return True

    def publish(self):
        self.status = AssessmentStatus.PUBLISHED
        if not self.published_at:
            self.published_at = timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])

    def recompute_total_points(self):
        total = sum(aq.points for aq in self.assessment_questions.all())
        self.total_points = total
        self.save(update_fields=["total_points", "updated_at"])


class AssessmentQuestion(models.Model):
    """A question attached to an assessment, with per-assessment points."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="assessment_questions",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name="assessment_links",
    )
    position = models.PositiveSmallIntegerField(_("position"), default=1)
    points = models.DecimalField(_("points"), max_digits=6, decimal_places=2, default=1)

    class Meta:
        verbose_name = _("assessment question")
        verbose_name_plural = _("assessment questions")
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "position"],
                name="uniq_assessment_question_position",
            ),
            models.UniqueConstraint(
                fields=["assessment", "question"],
                name="uniq_assessment_question",
            ),
        ]


class AssessmentCodeAttempt(models.Model):
    """
    Audit log of every code-entry attempt (success or failure).
    Used for rate limiting and integrity review.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="code_attempts",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assessment_code_attempts",
    )

    success = models.BooleanField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("assessment code attempt")
        verbose_name_plural = _("assessment code attempts")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["assessment", "student", "-created_at"]),
            models.Index(fields=["success"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.student_id} → {self.assessment_id} "
            f"({'ok' if self.success else 'fail'})"
        )


# ──────────────────────────────────────────────────────────────────────
# Attempt (database doc §18.3)
# ──────────────────────────────────────────────────────────────────────
class AssessmentAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assessment_attempts",
    )

    attempt_number = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=AttemptStatus.choices,
        default=AttemptStatus.IN_PROGRESS,
        db_index=True,
    )

    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    entered_at = models.DateTimeField(
        _("entered at"),
        null=True,
        blank=True,
        help_text=_("When the student successfully entered the code."),
    )
    served_questions = models.JSONField(
        _("served questions"),
        default=list,
        blank=True,
        help_text=_(
            "List of AssessmentQuestion IDs served for this attempt. "
            "Empty means all questions — populated only when randomization "
            "or pool selection is active."
        ),
    )
    total_score = models.DecimalField(
        _("score"),
        max_digits=8,
        decimal_places=2,
        default=0,
    )
    percentage = models.DecimalField(
        _("percentage"),
        max_digits=6,
        decimal_places=2,
        default=0,
    )

    graded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("assessment attempt")
        verbose_name_plural = _("assessment attempts")
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "student", "attempt_number"],
                name="uniq_attempt_number",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["assessment", "student"]),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} → {self.assessment_id} #{self.attempt_number}"


class StudentAnswer(models.Model):
    """One answer for one assessment question within an attempt."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    attempt = models.ForeignKey(
        AssessmentAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    assessment_question = models.ForeignKey(
        AssessmentQuestion,
        on_delete=models.PROTECT,
        related_name="answers",
    )

    answer_text = models.TextField(blank=True)
    selected_option_ids = models.JSONField(default=list, blank=True)
    numeric_answer = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    answer_data = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Flexible payload for MATCHING and complex types."),
    )

    is_correct = models.BooleanField(null=True, blank=True)
    score = models.DecimalField(
        _("score"),
        max_digits=6,
        decimal_places=2,
        default=0,
    )
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="answers_graded",
    )
    graded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("student answer")
        verbose_name_plural = _("student answers")
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "assessment_question"],
                name="uniq_answer_per_question",
            ),
        ]
