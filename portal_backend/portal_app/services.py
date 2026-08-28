from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    Appointment,
    AppointmentHistory,
    NotificationOutbox,
    Patient,
    Provider,
)



# Custom Exceptions


class AppointmentServiceError(Exception):
    """Base exception for appointment business errors."""


class InvalidAppointmentTransition(AppointmentServiceError):
    """Raised when an appointment state transition is invalid."""


class AppointmentVersionConflict(AppointmentServiceError):
    """
    Raised when the client is working with stale appointment data.

    This is Problem 1:
    optimistic concurrency control.
    """


class AppointmentOverlapError(AppointmentServiceError):
    """
    Raised when confirming/rescheduling would cause
    overlapping confirmed appointments for the same provider.
    """


class AppointmentNotFound(AppointmentServiceError):
    """Raised when the appointment does not exist."""


class AppointmentPermissionError(AppointmentServiceError):
    """Raised when an actor is not allowed to perform the operation."""



# Internal Helpers



def _get_appointment(appointment_id):
    """
    Retrieve the current appointment.

    We deliberately don't use this function as the concurrency
    mechanism. The version check + conditional UPDATE is the
    actual concurrency mechanism.
    """

    try:
        return Appointment.objects.select_related(
            "patient",
            "provider",
        ).get(pk=appointment_id)

    except Appointment.DoesNotExist:
        raise AppointmentNotFound(
            f"Appointment {appointment_id} does not exist."
        )


def _check_version(appointment, expected_version):
    """
    Check whether the client is operating on the latest version.

    Example:

        Client has version 3
        Database has version 4

        => stale request
        => reject with conflict
    """

    if expected_version != appointment.version:
        raise AppointmentVersionConflict(
            "This appointment was modified by someone else. "
            "Please refresh and review the latest appointment details."
        )


def _create_history(
    *,
    appointment,
    action,
    actor_type,
    actor_name,
    old_status,
    new_status,
    old_scheduled_at,
    new_scheduled_at,
):
    """
    Create an audit event.

    This is intentionally explicit instead of using signals.
    """

    return AppointmentHistory.objects.create(
        appointment=appointment,
        action=action,
        actor_type=actor_type,
        actor_name=actor_name,
        old_status=old_status,
        new_status=new_status,
        old_scheduled_at=old_scheduled_at,
        new_scheduled_at=new_scheduled_at,
    )


def _create_confirmation_notification(appointment):
    """
    Create a durable notification record.

    No real email/SMS is sent here.

    The outbox record is created inside the same database
    transaction as the appointment confirmation.

    A production worker can consume this record asynchronously.
    """

    message = (
        f"Your appointment with {appointment.provider.name} "
        f"has been confirmed for "
        f"{appointment.scheduled_at.isoformat()}."
    )

    return NotificationOutbox.objects.create(
        appointment=appointment,
        channel=NotificationOutbox.Channel.EMAIL,
        recipient=appointment.patient.email,
        message=message,
        status=NotificationOutbox.Status.PENDING,
    )


def _send_notification_stub(notification_id):
    """
    Assignment notification stub.

    We intentionally don't call an external email/SMS provider.

    IMPORTANT:
    The callback is defensive. A notification failure must never
    change the already-committed appointment confirmation.
    """

    try:
        notification = NotificationOutbox.objects.get(
            pk=notification_id
        )

        print(
            "WOULD SEND EMAIL: "
            f"to={notification.recipient}, "
            f"message={notification.message}"
        )

        # For this assignment, consider the stub delivery successful.
        notification.status = NotificationOutbox.Status.SENT
        notification.processed_at = timezone.now()

        notification.save(
            update_fields=[
                "status",
                "processed_at",
            ]
        )

    except Exception as exc:
        # The appointment is already committed.
        # Notification failure must not roll back the confirmation.
        print(
            "NOTIFICATION FAILED: "
            f"notification_id={notification_id}, "
            f"error={exc}"
        )



# Create Appointment



@transaction.atomic
def request_appointment(
    *,
    patient: Patient,
    provider: Provider,
    scheduled_at,
    appointment_type,
    reason,
    duration_minutes=60,
):
    """
    Patient requests a new appointment.

    New appointment always starts as PENDING.

    No availability check is required here because the assignment
    explicitly allows multiple pending requests.
    """

    if scheduled_at <= timezone.now():
        raise AppointmentServiceError(
            "Appointment date/time must be in the future."
        )

    appointment = Appointment.objects.create(
        patient=patient,
        provider=provider,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        appointment_type=appointment_type,
        reason=reason,
        status=Appointment.Status.PENDING,
        version=1,
    )

    _create_history(
        appointment=appointment,
        action=AppointmentHistory.Action.CREATED,
        actor_type=AppointmentHistory.ActorType.PATIENT,
        actor_name=patient.name,
        old_status=None,
        new_status=Appointment.Status.PENDING,
        old_scheduled_at=None,
        new_scheduled_at=appointment.scheduled_at,
    )

    return appointment



# Confirm Appointment



def confirm_appointment(
    *,
    appointment_id,
    provider: Provider,
    expected_version,
):
    """
    Confirm a pending appointment.

    Problem 1:
        expected_version protects against stale UI.

    Problem 4:
        database trigger protects the final no-overlap invariant.

    Problem 3:
        notification is persisted as an outbox event and the
        actual notification stub runs after the DB transaction.
    """

    with transaction.atomic():

        appointment = _get_appointment(appointment_id)

        # ----------------------------------------------------
        # Authorization
        # ----------------------------------------------------

        if appointment.provider_id != provider.id:
            raise AppointmentPermissionError(
                "This appointment does not belong to this provider."
            )

        # ----------------------------------------------------
        # Optimistic concurrency check
        # ----------------------------------------------------

        _check_version(
            appointment,
            expected_version,
        )

        # ----------------------------------------------------
        # State-machine validation
        # ----------------------------------------------------

        if appointment.status != Appointment.Status.PENDING:
            raise InvalidAppointmentTransition(
                "Only pending appointments can be confirmed."
            )

        old_status = appointment.status
        old_scheduled_at = appointment.scheduled_at
        old_version = appointment.version

        # ----------------------------------------------------
        # Conditional UPDATE
        # ----------------------------------------------------
        #
        # This is an important part of Problem 1.
        #
        # We don't simply call:
        #
        #     appointment.save()
        #
        # after checking the version.
        #
        # Instead we make the version part of the UPDATE
        # condition.
        #
        # Therefore two requests with version=3 cannot both
        # successfully modify version=3.
        # ----------------------------------------------------

        # updated = Appointment.objects.filter(
        #     pk=appointment.id,
        #     version=old_version,
        #     status=Appointment.Status.PENDING,
        # ).update(
        #     status=Appointment.Status.CONFIRMED,
        #     version=old_version + 1,
        #     updated_at=timezone.now(),
        # )
        try:
            updated = Appointment.objects.filter(
                pk=appointment.id,
                version=old_version,
                status=Appointment.Status.PENDING,
            ).update(
                status=Appointment.Status.CONFIRMED,
                version=old_version + 1,
                updated_at=timezone.now(),
            )

        except IntegrityError as exc:
            if "overlapping confirmed appointment" in str(exc).lower():
                raise AppointmentOverlapError(
                    "The provider already has a confirmed "
                    "appointment during this time."
                ) from exc

            raise

        if updated == 0:
            raise AppointmentVersionConflict(
                "This appointment was modified by someone else. "
                "Please refresh and review the latest appointment."
            )

        # Refresh so history/notification use the new state.
        appointment.refresh_from_db()

        # ----------------------------------------------------
        # Audit history
        # ----------------------------------------------------

        _create_history(
            appointment=appointment,
            action=AppointmentHistory.Action.CONFIRMED,
            actor_type=AppointmentHistory.ActorType.PROVIDER,
            actor_name=provider.name,
            old_status=old_status,
            new_status=appointment.status,
            old_scheduled_at=old_scheduled_at,
            new_scheduled_at=appointment.scheduled_at,
        )

        # ----------------------------------------------------
        # Notification outbox
        # ----------------------------------------------------

        notification = _create_confirmation_notification(
            appointment
        )

        # ----------------------------------------------------
        # Run stub AFTER successful transaction commit.
        # ----------------------------------------------------

        transaction.on_commit(
            lambda notification_id=notification.id: (
                _send_notification_stub(notification_id)
            )
        )

        return appointment



# Reschedule Appointment



def reschedule_appointment(
    *,
    appointment_id,
    provider: Provider,
    new_scheduled_at,
    expected_version,
):
    """
    Provider changes the appointment time.

    Both pending and confirmed appointments can be rescheduled.

    Important:
        If a confirmed appointment is moved to an overlapping
        time, the database trigger rejects the UPDATE.

    Problem 1:
        expected_version prevents a stale provider screen from
        overwriting another change.
    """

    if new_scheduled_at <= timezone.now():
        raise AppointmentServiceError(
            "Appointment date/time must be in the future."
        )

    with transaction.atomic():

        appointment = _get_appointment(appointment_id)

        # ----------------------------------------------------
        # Authorization
        # ----------------------------------------------------

        if appointment.provider_id != provider.id:
            raise AppointmentPermissionError(
                "This appointment does not belong to this provider."
            )

        # ----------------------------------------------------
        # Version check
        # ----------------------------------------------------

        _check_version(
            appointment,
            expected_version,
        )

        # ----------------------------------------------------
        # State validation
        # ----------------------------------------------------

        if appointment.status == Appointment.Status.CANCELLED:
            raise InvalidAppointmentTransition(
                "Cancelled appointments cannot be rescheduled."
            )

        old_status = appointment.status
        old_scheduled_at = appointment.scheduled_at
        old_version = appointment.version

        # ----------------------------------------------------
        # Conditional UPDATE
        # ----------------------------------------------------

        try:
            updated = Appointment.objects.filter(
                pk=appointment.id,
                version=old_version,
                status=old_status,
            ).update(
                scheduled_at=new_scheduled_at,
                version=old_version + 1,
                updated_at=timezone.now(),
            )

        except IntegrityError as exc:
            # SQLite trigger rejected an overlapping confirmed
            # appointment.
            if "overlapping confirmed appointment" in str(exc):
                raise AppointmentOverlapError(
                    "The provider already has a confirmed "
                    "appointment during this time."
                ) from exc

            raise

        if updated == 0:
            raise AppointmentVersionConflict(
                "This appointment was modified by someone else. "
                "Please refresh and try again."
            )

        appointment.refresh_from_db()

        # ----------------------------------------------------
        # Audit history
        # ----------------------------------------------------

        _create_history(
            appointment=appointment,
            action=AppointmentHistory.Action.RESCHEDULED,
            actor_type=AppointmentHistory.ActorType.PROVIDER,
            actor_name=provider.name,
            old_status=old_status,
            new_status=appointment.status,
            old_scheduled_at=old_scheduled_at,
            new_scheduled_at=appointment.scheduled_at,
        )

        return appointment



# Cancel Appointment



def cancel_appointment(
    *,
    appointment_id,
    patient: Patient,
    expected_version,
):
    """
    Patient cancels a confirmed appointment.

    Pending appointments cannot be cancelled according to
    the assignment.
    """

    with transaction.atomic():

        appointment = _get_appointment(appointment_id)

        # ----------------------------------------------------
        # Authorization
        # ----------------------------------------------------

        if appointment.patient_id != patient.id:
            raise AppointmentPermissionError(
                "This appointment does not belong to this patient."
            )

        # ----------------------------------------------------
        # Optimistic concurrency
        # ----------------------------------------------------

        _check_version(
            appointment,
            expected_version,
        )

        # ----------------------------------------------------
        # State validation
        # ----------------------------------------------------

        if appointment.status != Appointment.Status.CONFIRMED:
            raise InvalidAppointmentTransition(
                "Only confirmed appointments can be cancelled."
            )

        old_status = appointment.status
        old_scheduled_at = appointment.scheduled_at
        old_version = appointment.version

        # ----------------------------------------------------
        # Conditional UPDATE
        # ----------------------------------------------------

        updated = Appointment.objects.filter(
            pk=appointment.id,
            version=old_version,
            status=Appointment.Status.CONFIRMED,
        ).update(
            status=Appointment.Status.CANCELLED,
            version=old_version + 1,
            updated_at=timezone.now(),
        )

        if updated == 0:
            raise AppointmentVersionConflict(
                "This appointment was modified by someone else. "
                "Please refresh and review the latest appointment."
            )

        appointment.refresh_from_db()

        # ----------------------------------------------------
        # Audit
        # ----------------------------------------------------

        _create_history(
            appointment=appointment,
            action=AppointmentHistory.Action.CANCELLED,
            actor_type=AppointmentHistory.ActorType.PATIENT,
            actor_name=patient.name,
            old_status=old_status,
            new_status=appointment.status,
            old_scheduled_at=old_scheduled_at,
            new_scheduled_at=appointment.scheduled_at,
        )

        return appointment