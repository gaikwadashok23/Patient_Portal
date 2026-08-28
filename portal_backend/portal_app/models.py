from datetime import timedelta

from django.core.validators import MinValueValidator
from django.db import models


class Patient(models.Model):
    """
    Patient participating in the appointment system.

    Authentication is intentionally omitted because the assignment
    explicitly says that no real authentication is required.
    """

    name = models.CharField(max_length=120)

    email = models.EmailField(
        unique=True,
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Provider(models.Model):
    """
    Healthcare provider who owns appointments.
    """

    name = models.CharField(
        max_length=120,
    )

    specialty = models.CharField(
        max_length=120,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Appointment(models.Model):
    """
    Current state of an appointment.

    Important:
    - version -> optimistic concurrency control for Problem 1
    - status -> appointment state machine
    - scheduled_at + duration_minutes -> appointment interval
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    class AppointmentType(models.TextChoices):
        CONSULTATION = "consultation", "Consultation"
        FOLLOW_UP = "follow_up", "Follow-up"
        THERAPY = "therapy", "Therapy"
        OTHER = "other", "Other"

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="appointments",
    )

    provider = models.ForeignKey(
        Provider,
        on_delete=models.PROTECT,
        related_name="appointments",
    )

    scheduled_at = models.DateTimeField()

    duration_minutes = models.PositiveIntegerField(
        default=60,
        validators=[
            MinValueValidator(1),
        ],
    )

    appointment_type = models.CharField(
        max_length=30,
        choices=AppointmentType.choices,
        default=AppointmentType.CONSULTATION,
    )

    reason = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Optimistic concurrency control.
    #
    # Every successful appointment mutation increments this value.
    # A client must send the version it last observed when performing
    # a state-changing operation.
    version = models.PositiveIntegerField(
        default=1,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["scheduled_at"]

        indexes = [
            models.Index(
                fields=["patient", "scheduled_at"],
                name="appt_patient_time_idx",
            ),
            models.Index(
                fields=["provider", "scheduled_at"],
                name="appt_provider_time_idx",
            ),
            models.Index(
                fields=["status", "scheduled_at"],
                name="appt_status_time_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.patient.name} - "
            f"{self.provider.name} - "
            f"{self.scheduled_at}"
        )

    @property
    def ends_at(self):
        """
        Return the calculated end time of the appointment.

        We intentionally store:
            scheduled_at + duration_minutes

        instead of storing a separate end_at column.

        This prevents two independent time values from becoming
        inconsistent.
        """
        return self.scheduled_at + timedelta(
            minutes=self.duration_minutes
        )


class AppointmentHistory(models.Model):
    """
    Immutable audit record for appointment changes.

    Appointment:
        stores the CURRENT state.

    AppointmentHistory:
        stores what happened to the appointment over time.

    This allows us to answer:
        - Who changed it?
        - When did it change?
        - What was the previous value?
        - What is the new value?
    """

    class Action(models.TextChoices):
        CREATED = "created", "Created"
        CONFIRMED = "confirmed", "Confirmed"
        RESCHEDULED = "rescheduled", "Rescheduled"
        CANCELLED = "cancelled", "Cancelled"

    class ActorType(models.TextChoices):
        PATIENT = "patient", "Patient"
        PROVIDER = "provider", "Provider"
        SYSTEM = "system", "System"

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="history",
    )

    action = models.CharField(
        max_length=30,
        choices=Action.choices,
    )

    actor_type = models.CharField(
        max_length=20,
        choices=ActorType.choices,
    )

    # Real authentication is intentionally not implemented.
    # Therefore we store the actor's name for the audit record.
    actor_name = models.CharField(
        max_length=120,
    )

    # Values BEFORE the operation.
    old_status = models.CharField(
        max_length=20,
        choices=Appointment.Status.choices,
        null=True,
        blank=True,
    )

    old_scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Values AFTER the operation.
    new_status = models.CharField(
        max_length=20,
        choices=Appointment.Status.choices,
        null=True,
        blank=True,
    )

    new_scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["appointment", "-created_at"],
                name="appt_history_time_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Appointment {self.appointment_id} - "
            f"{self.action} - "
            f"{self.created_at}"
        )


class NotificationOutbox(models.Model):
    """
    Lightweight transactional outbox.

    When a provider confirms an appointment, the appointment
    confirmation and notification record can be created as part
    of the same database transaction.

    The actual delivery is intentionally stubbed for this assignment.

    Production evolution:
        DB outbox -> worker/SQS/Celery -> email/SMS provider
    """

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.EMAIL,
    )

    recipient = models.CharField(
        max_length=255,
    )

    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["created_at"]

        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="notification_status_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.channel} notification to "
            f"{self.recipient} ({self.status})"
        )