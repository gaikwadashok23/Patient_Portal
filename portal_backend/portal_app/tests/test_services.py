from datetime import timedelta

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from portal_app.models import (
    Appointment,
    AppointmentHistory,
    NotificationOutbox,
    Patient,
    Provider,
)
from portal_app.services import (
    AppointmentOverlapError,
    AppointmentServiceError,
    AppointmentVersionConflict,
    InvalidAppointmentTransition,
    cancel_appointment,
    confirm_appointment,
    request_appointment,
    reschedule_appointment,
)


class AppointmentServiceTestCase(TestCase):
    """
    Tests for the appointment service layer.

    These tests focus on business behavior rather than HTTP.

    API tests will be added later when we build the DRF layer.
    """

    def setUp(self):
        """
        Create common test data before every test.
        """

        self.patient = Patient.objects.create(
            name="Ashok Gaikwad",
            email="ashok@example.com",
            phone="9876543210",
        )

        self.second_patient = Patient.objects.create(
            name="Test Patient",
            email="patient2@example.com",
            phone="9876543211",
        )

        self.provider = Provider.objects.create(
            name="Dr. Sarah Smith",
            specialty="Behavioral Health",
        )

        self.second_provider = Provider.objects.create(
            name="Dr. John Doe",
            specialty="Psychiatry",
        )

        # Always use a future time for appointment tests.
        self.start_time = (
            timezone.now()
            + timedelta(days=1)
        ).replace(
            second=0,
            microsecond=0,
        )

    # ========================================================
    # Helper
    # ========================================================

    def create_pending_appointment(
        self,
        *,
        patient=None,
        provider=None,
        scheduled_at=None,
        duration_minutes=60,
    ):
        """
        Create an appointment through the service layer.

        Using the service instead of Appointment.objects.create()
        ensures the test also verifies our normal creation flow.
        """

        return request_appointment(
            patient=patient or self.patient,
            provider=provider or self.provider,
            scheduled_at=scheduled_at or self.start_time,
            appointment_type=Appointment.AppointmentType.CONSULTATION,
            reason="Routine appointment",
            duration_minutes=duration_minutes,
        )

    # ========================================================
    # 1. Appointment creation
    # ========================================================

    def test_patient_can_request_appointment(self):
        """
        A new appointment should start in PENDING state.
        """

        appointment = self.create_pending_appointment()

        self.assertEqual(
            appointment.status,
            Appointment.Status.PENDING,
        )

        self.assertEqual(
            appointment.version,
            1,
        )

        self.assertEqual(
            appointment.patient,
            self.patient,
        )

        self.assertEqual(
            appointment.provider,
            self.provider,
        )

        self.assertEqual(
            appointment.duration_minutes,
            60,
        )

    def test_creation_creates_history_record(self):
        """
        Creating an appointment should create an audit record.
        """

        appointment = self.create_pending_appointment()

        history = AppointmentHistory.objects.filter(
            appointment=appointment
        )

        self.assertEqual(
            history.count(),
            1,
        )

        event = history.first()

        self.assertEqual(
            event.action,
            AppointmentHistory.Action.CREATED,
        )

        self.assertEqual(
            event.actor_type,
            AppointmentHistory.ActorType.PATIENT,
        )

        self.assertEqual(
            event.actor_name,
            self.patient.name,
        )

        self.assertIsNone(
            event.old_status
        )

        self.assertEqual(
            event.new_status,
            Appointment.Status.PENDING,
        )

    def test_past_appointment_cannot_be_requested(self):
        """
        Appointments must be requested for a future time.
        """

        with self.assertRaises(AppointmentServiceError):
            self.create_pending_appointment(
                scheduled_at=timezone.now() - timedelta(hours=1)
            )

    # ========================================================
    # 2. Confirmation
    # ========================================================

    def test_provider_can_confirm_pending_appointment(self):
        """
        PENDING -> CONFIRMED should succeed for the assigned provider.
        """

        appointment = self.create_pending_appointment()

        confirmed = confirm_appointment(
            appointment_id=appointment.id,
            provider=self.provider,
            expected_version=1,
        )

        confirmed.refresh_from_db()

        self.assertEqual(
            confirmed.status,
            Appointment.Status.CONFIRMED,
        )

        self.assertEqual(
            confirmed.version,
            2,
        )

    def test_confirmation_creates_history(self):
        """
        Confirmation should preserve the previous state in history.
        """

        appointment = self.create_pending_appointment()

        confirm_appointment(
            appointment_id=appointment.id,
            provider=self.provider,
            expected_version=1,
        )

        events = AppointmentHistory.objects.filter(
            appointment=appointment
        ).order_by("created_at")

        self.assertEqual(
            events.count(),
            2,
        )

        confirmation_event = events.last()

        self.assertEqual(
            confirmation_event.action,
            AppointmentHistory.Action.CONFIRMED,
        )

        self.assertEqual(
            confirmation_event.old_status,
            Appointment.Status.PENDING,
        )

        self.assertEqual(
            confirmation_event.new_status,
            Appointment.Status.CONFIRMED,
        )

        self.assertEqual(
            confirmation_event.actor_type,
            AppointmentHistory.ActorType.PROVIDER,
        )

    

    def test_confirmation_creates_notification_outbox(self):
        """
        Confirmation must create a durable notification record.

        The appointment confirmation itself must not depend on
        successful notification delivery.
        """

        appointment = self.create_pending_appointment()

        confirm_appointment(
            appointment_id=appointment.id,
            provider=self.provider,
            expected_version=1,
        )

        notification = NotificationOutbox.objects.get(
            appointment=appointment
        )

        self.assertEqual(
            notification.channel,
            NotificationOutbox.Channel.EMAIL,
        )

        self.assertEqual(
            notification.recipient,
            self.patient.email,
        )

        self.assertEqual(
            notification.message.startswith(
                "Your appointment with"
            ),
            True,
        )
    def test_wrong_provider_cannot_confirm_appointment(self):
        """
        A provider can only modify their own appointments.
        """

        appointment = self.create_pending_appointment()

        with self.assertRaises(Exception):
            confirm_appointment(
                appointment_id=appointment.id,
                provider=self.second_provider,
                expected_version=1,
            )

    # ========================================================
    # 3. Cancellation
    # ========================================================

    def test_patient_can_cancel_confirmed_appointment(self):
        """
        CONFIRMED -> CANCELLED should succeed.
        """

        appointment = self.create_pending_appointment()

        confirm_appointment(
            appointment_id=appointment.id,
            provider=self.provider,
            expected_version=1,
        )

        cancelled = cancel_appointment(
            appointment_id=appointment.id,
            patient=self.patient,
            expected_version=2,
        )

        cancelled.refresh_from_db()

        self.assertEqual(
            cancelled.status,
            Appointment.Status.CANCELLED,
        )

        self.assertEqual(
            cancelled.version,
            3,
        )

    def test_pending_appointment_cannot_be_cancelled(self):
        """
        Assignment requirement:

            Pending appointments cannot be cancelled.
        """

        appointment = self.create_pending_appointment()

        with self.assertRaises(InvalidAppointmentTransition):
            cancel_appointment(
                appointment_id=appointment.id,
                patient=self.patient,
                expected_version=1,
            )

        appointment.refresh_from_db()

        self.assertEqual(
            appointment.status,
            Appointment.Status.PENDING,
        )

    def test_cancellation_creates_history(self):
        """
        Cancellation should be recorded in the audit trail.
        """

        appointment = self.create_pending_appointment()

        confirm_appointment(
            appointment_id=appointment.id,
            provider=self.provider,
            expected_version=1,
        )

        cancel_appointment(
            appointment_id=appointment.id,
            patient=self.patient,
            expected_version=2,
        )

        event = AppointmentHistory.objects.filter(
            appointment=appointment,
            action=AppointmentHistory.Action.CANCELLED,
        ).get()

        self.assertEqual(
            event.old_status,
            Appointment.Status.CONFIRMED,
        )

        self.assertEqual(
            event.new_status,
            Appointment.Status.CANCELLED,
        )

        self.assertEqual(
            event.actor_type,
            AppointmentHistory.ActorType.PATIENT,
        )

    # ========================================================
    # 4. Problem 1 - Optimistic Concurrency
    # ========================================================

    def test_stale_version_is_rejected(self):
        """
        Problem 1:

        Client sees version 1.

        Provider changes the appointment.
        Version becomes 2.

        Client sends version 1.

        The stale request must be rejected.
        """

        appointment = self.create_pending_appointment()

        # Provider confirms it.
        confirm_appointment(
            appointment_id=appointment.id,
            provider=self.provider,
            expected_version=1,
        )

        # Patient still thinks the appointment is version 1.
        with self.assertRaises(AppointmentVersionConflict):
            cancel_appointment(
                appointment_id=appointment.id,
                patient=self.patient,
                expected_version=1,
            )

        appointment.refresh_from_db()

        # The stale request must NOT cancel it.
        self.assertEqual(
            appointment.status,
            Appointment.Status.CONFIRMED,
        )

        self.assertEqual(
            appointment.version,
            2,
        )

    def test_same_version_cannot_be_used_twice(self):
        """
        Once version 1 has been consumed, another request
        using version 1 must fail.
        """

        appointment = self.create_pending_appointment()

        confirm_appointment(
            appointment_id=appointment.id,
            provider=self.provider,
            expected_version=1,
        )

        with self.assertRaises(
            AppointmentVersionConflict
        ):
            confirm_appointment(
                appointment_id=appointment.id,
                provider=self.provider,
                expected_version=1,
            )

    # ========================================================
    # 5. Rescheduling
    # ========================================================

    def test_provider_can_reschedule_pending_appointment(self):
        """
        A provider can change the requested time of a pending
        appointment.
        """

        appointment = self.create_pending_appointment()

        new_time = (
            self.start_time
            + timedelta(hours=2)
        )

        updated = reschedule_appointment(
            appointment_id=appointment.id,
            provider=self.provider,
            new_scheduled_at=new_time,
            expected_version=1,
        )

        updated.refresh_from_db()

        self.assertEqual(
            updated.scheduled_at,
            new_time,
        )

        self.assertEqual(
            updated.status,
            Appointment.Status.PENDING,
        )

        self.assertEqual(
            updated.version,
            2,
        )

    def test_provider_can_reschedule_confirmed_appointment(self):
        """
        A confirmed appointment remains confirmed after rescheduling.
        """

        appointment = self.create_pending_appointment()

        confirm_appointment(
            appointment_id=appointment.id,
            provider=self.provider,
            expected_version=1,
        )

        new_time = (
            self.start_time
            + timedelta(hours=3)
        )

        updated = reschedule_appointment(
            appointment_id=appointment.id,
            provider=self.provider,
            new_scheduled_at=new_time,
            expected_version=2,
        )

        updated.refresh_from_db()

        self.assertEqual(
            updated.status,
            Appointment.Status.CONFIRMED,
        )

        self.assertEqual(
            updated.scheduled_at,
            new_time,
        )

        self.assertEqual(
            updated.version,
            3,
        )

    def test_reschedule_creates_history(self):
        """
        Problem 2:

        Previous and new appointment times must be preserved.
        """

        appointment = self.create_pending_appointment()

        new_time = (
            self.start_time
            + timedelta(hours=4)
        )

        reschedule_appointment(
            appointment_id=appointment.id,
            provider=self.provider,
            new_scheduled_at=new_time,
            expected_version=1,
        )

        event = AppointmentHistory.objects.filter(
            appointment=appointment,
            action=AppointmentHistory.Action.RESCHEDULED,
        ).get()

        self.assertEqual(
            event.old_scheduled_at,
            self.start_time,
        )

        self.assertEqual(
            event.new_scheduled_at,
            new_time,
        )

    def test_cancelled_appointment_cannot_be_rescheduled(self):
        """
        CANCELLED is a terminal state.
        """

        appointment = self.create_pending_appointment()

        confirm_appointment(
            appointment_id=appointment.id,
            provider=self.provider,
            expected_version=1,
        )

        cancel_appointment(
            appointment_id=appointment.id,
            patient=self.patient,
            expected_version=2,
        )

        with self.assertRaises(
            InvalidAppointmentTransition
        ):
            reschedule_appointment(
                appointment_id=appointment.id,
                provider=self.provider,
                new_scheduled_at=(
                    self.start_time
                    + timedelta(hours=5)
                ),
                expected_version=3,
            )

    # ========================================================
    # 6. Problem 4 - Overlap
    # ========================================================

    def test_overlapping_confirmed_appointments_are_rejected(self):
        """
        Problem 4:

        Provider already has:

            10:00 -> 11:00 CONFIRMED

        Another appointment:

            10:30 -> 11:30 PENDING

        Confirmation must fail.
        """

        first = self.create_pending_appointment(
            scheduled_at=self.start_time,
            duration_minutes=60,
        )

        confirm_appointment(
            appointment_id=first.id,
            provider=self.provider,
            expected_version=1,
        )

        second = self.create_pending_appointment(
            patient=self.second_patient,
            scheduled_at=(
                self.start_time
                + timedelta(minutes=30)
            ),
            duration_minutes=60,
        )

        with self.assertRaises(
            AppointmentOverlapError
        ):
            confirm_appointment(
                appointment_id=second.id,
                provider=self.provider,
                expected_version=1,
            )

        second.refresh_from_db()

        # Important:
        # Failed confirmation must leave the appointment pending.
        self.assertEqual(
            second.status,
            Appointment.Status.PENDING,
        )

    def test_adjacent_confirmed_appointments_are_allowed(self):
        """
        These appointments touch but do not overlap:

            10:00 -> 11:00
            11:00 -> 12:00
        """

        first = self.create_pending_appointment(
            scheduled_at=self.start_time,
            duration_minutes=60,
        )

        confirm_appointment(
            appointment_id=first.id,
            provider=self.provider,
            expected_version=1,
        )

        second = self.create_pending_appointment(
            patient=self.second_patient,
            scheduled_at=(
                self.start_time
                + timedelta(hours=1)
            ),
            duration_minutes=60,
        )

        confirmed = confirm_appointment(
            appointment_id=second.id,
            provider=self.provider,
            expected_version=1,
        )

        confirmed.refresh_from_db()

        self.assertEqual(
            confirmed.status,
            Appointment.Status.CONFIRMED,
        )

    def test_different_providers_can_have_overlapping_appointments(self):
        """
        Provider A and Provider B can have appointments at the
        same time because the constraint is provider-specific.
        """

        first = self.create_pending_appointment(
            scheduled_at=self.start_time,
        )

        confirm_appointment(
            appointment_id=first.id,
            provider=self.provider,
            expected_version=1,
        )

        second = self.create_pending_appointment(
            patient=self.second_patient,
            provider=self.second_provider,
            scheduled_at=self.start_time,
        )

        confirmed = confirm_appointment(
            appointment_id=second.id,
            provider=self.second_provider,
            expected_version=1,
        )

        confirmed.refresh_from_db()

        self.assertEqual(
            confirmed.status,
            Appointment.Status.CONFIRMED,
        )

    def test_rescheduling_confirmed_appointment_into_overlap_fails(self):
        """
        A confirmed appointment cannot be moved into another
        confirmed appointment's time range.
        """

        first = self.create_pending_appointment(
            scheduled_at=self.start_time,
        )

        confirm_appointment(
            appointment_id=first.id,
            provider=self.provider,
            expected_version=1,
        )

        second = self.create_pending_appointment(
            patient=self.second_patient,
            scheduled_at=(
                self.start_time
                + timedelta(hours=2)
            ),
        )

        confirm_appointment(
            appointment_id=second.id,
            provider=self.provider,
            expected_version=1,
        )

        overlapping_time = (
            self.start_time
            + timedelta(minutes=30)
        )

        with self.assertRaises(
            AppointmentOverlapError
        ):
            reschedule_appointment(
                appointment_id=second.id,
                provider=self.provider,
                new_scheduled_at=overlapping_time,
                expected_version=2,
            )

        second.refresh_from_db()

        # The failed operation must not change the original time.
        self.assertEqual(
            second.scheduled_at,
            self.start_time + timedelta(hours=2),
        )

    # ========================================================
    # 7. Appointment interval
    # ========================================================

    def test_appointment_end_time_is_calculated_correctly(self):
        """
        The model should correctly calculate the end time.
        """

        appointment = self.create_pending_appointment(
            duration_minutes=45,
        )

        expected_end = (
            self.start_time
            + timedelta(minutes=45)
        )

        self.assertEqual(
            appointment.ends_at,
            expected_end,
        )