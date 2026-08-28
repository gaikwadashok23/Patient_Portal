from django.utils import timezone
from rest_framework import serializers

from .models import (
    Appointment,
    AppointmentHistory,
    NotificationOutbox,
    Patient,
    Provider,
)


# ============================================================
# Patient / Provider serializers
# ============================================================


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = [
            "id",
            "name",
            "email",
            "phone",
        ]
        read_only_fields = ["id"]


class ProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = [
            "id",
            "name",
            "specialty",
        ]
        read_only_fields = ["id"]


# ============================================================
# Appointment list/detail serializer
# ============================================================


class AppointmentSerializer(serializers.ModelSerializer):
    """
    Read representation of an appointment.

    The frontend gets enough information to render the
    appointment without making additional requests for
    patient/provider names.
    """

    patient_name = serializers.CharField(
        source="patient.name",
        read_only=True,
    )

    provider_name = serializers.CharField(
        source="provider.name",
        read_only=True,
    )

    provider_specialty = serializers.CharField(
        source="provider.specialty",
        read_only=True,
    )

    ends_at = serializers.DateTimeField(
        read_only=True,
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    appointment_type_display = serializers.CharField(
        source="get_appointment_type_display",
        read_only=True,
    )

    class Meta:
        model = Appointment

        fields = [
            "id",
            "patient",
            "patient_name",
            "provider",
            "provider_name",
            "provider_specialty",
            "scheduled_at",
            "ends_at",
            "duration_minutes",
            "appointment_type",
            "appointment_type_display",
            "reason",
            "status",
            "status_display",
            "version",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "patient_name",
            "provider_name",
            "provider_specialty",
            "ends_at",
            "status_display",
            "appointment_type_display",
            "status",
            "version",
            "created_at",
            "updated_at",
        ]


# ============================================================
# Create appointment request
# ============================================================


class AppointmentRequestSerializer(serializers.Serializer):
    """
    Validate a patient's appointment request.

    API contract intentionally uses:
        patient_id
        provider_id

    instead of exposing Django relationship field names
    directly in the request payload.
    """

    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=Patient.objects.all(),
        source="patient",
    )

    provider_id = serializers.PrimaryKeyRelatedField(
        queryset=Provider.objects.all(),
        source="provider",
    )

    scheduled_at = serializers.DateTimeField()

    duration_minutes = serializers.IntegerField(
        min_value=1,
        default=60,
    )

    appointment_type = serializers.ChoiceField(
        choices=Appointment.AppointmentType.choices,
        default=Appointment.AppointmentType.CONSULTATION,
    )

    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    def validate_scheduled_at(self, value):
        """
        Appointment must be scheduled in the future.
        """

        if value <= timezone.now():
            raise serializers.ValidationError(
                "Appointment date/time must be in the future."
            )

        return value


# ============================================================
# Confirm appointment
# ============================================================


class AppointmentConfirmSerializer(serializers.Serializer):
    """
    Input for:

        POST /appointments/<id>/confirm/

    expected_version is mandatory because confirmation is
    protected by optimistic concurrency control.
    """

    expected_version = serializers.IntegerField(
        min_value=1,
    )


# ============================================================
# Reschedule appointment
# ============================================================


class AppointmentRescheduleSerializer(serializers.Serializer):
    """
    Input for provider rescheduling.
    """

    new_scheduled_at = serializers.DateTimeField()

    expected_version = serializers.IntegerField(
        min_value=1,
    )

    def validate_new_scheduled_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError(
                "Appointment date/time must be in the future."
            )

        return value


# ============================================================
# Cancel appointment
# ============================================================


class AppointmentCancelSerializer(serializers.Serializer):
    """
    Input for patient cancellation.
    """

    expected_version = serializers.IntegerField(
        min_value=1,
    )


# ============================================================
# Appointment history
# ============================================================


class AppointmentHistorySerializer(
    serializers.ModelSerializer
):
    """
    Read-only representation of the audit trail.

    This is how the frontend can answer:

        Who changed it?
        When?
        What was it before?
        What is it now?
    """

    action_display = serializers.CharField(
        source="get_action_display",
        read_only=True,
    )

    actor_type_display = serializers.CharField(
        source="get_actor_type_display",
        read_only=True,
    )

    class Meta:
        model = AppointmentHistory

        fields = [
            "id",
            "appointment",
            "action",
            "action_display",
            "actor_type",
            "actor_type_display",
            "actor_name",
            "old_status",
            "old_scheduled_at",
            "new_status",
            "new_scheduled_at",
            "created_at",
        ]

        read_only_fields = fields


# ============================================================
# Notification
# ============================================================


class NotificationOutboxSerializer(
    serializers.ModelSerializer
):
    """
    Read-only representation of notification events.

    Useful for demonstrating Problem 3 during the review.
    """

    channel_display = serializers.CharField(
        source="get_channel_display",
        read_only=True,
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = NotificationOutbox

        fields = [
            "id",
            "appointment",
            "channel",
            "channel_display",
            "recipient",
            "message",
            "status",
            "status_display",
            "created_at",
            "processed_at",
        ]

        read_only_fields = fields