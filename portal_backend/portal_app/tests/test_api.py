from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from portal_app.models import (
    Appointment,
    AppointmentHistory,
    NotificationOutbox,
    Patient,
    Provider,
)


class AppointmentAPITestCase(APITestCase):
    """
    Integration tests for the DRF API.

    These tests intentionally exercise the complete path:

        HTTP
          ↓
        URL
          ↓
        View
          ↓
        Serializer
          ↓
        Service
          ↓
        Database
    """

    def setUp(self):
        self.patient = Patient.objects.create(
            name="Ashok Gaikwad",
            email="ashokgaikwad78652@gmail.com",
            phone="8805961403",
        )

        self.second_patient = Patient.objects.create(
            name="Kartik Gaikwad",
            email="kartikgaikwad224@gmail.com",
        )

        self.provider = Provider.objects.create(
            name="Dr. Rahul Mishra",
            specialty="Behavioral Health",
        )

        self.second_provider = Provider.objects.create(
            name="Dr. Kabir Singh",
            specialty="Psychiatry",
        )

        self.start_time = (
            timezone.now()
            + timedelta(days=2)
        ).replace(
            second=0,
            microsecond=0,
        )

    # ========================================================
    # Helpers
    # ========================================================

    def appointment_payload(
        self,
        *,
        patient_id=None,
        provider_id=None,
        scheduled_at=None,
    ):
        return {
            "patient_id": patient_id or self.patient.id,
            "provider_id": provider_id or self.provider.id,
            "scheduled_at": (
                scheduled_at or self.start_time
            ).isoformat(),
            "duration_minutes": 60,
            "appointment_type": (
                Appointment.AppointmentType.CONSULTATION
            ),
            "reason": "Routine consultation",
        }

    def create_appointment(self):
        response = self.client.post(
            reverse("appointment-list-create"),
            self.appointment_payload(),
            format="json",
        )

        if response.status_code != status.HTTP_201_CREATED:
            print("\n\nCREATE APPOINTMENT ERROR:")
            print("STATUS:", response.status_code)
            print("DATA:", response.data)
            print("PAYLOAD:", self.appointment_payload())

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        return response

    # ========================================================
    # Patient / Provider
    # ========================================================

    def test_patient_list_api(self):
        Patient.objects.create(
            name="Karan Patel",
            email="ashokgaikwad24816@gmail.com",
        )

        response = self.client.get(
            reverse("patient-list")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # print(f"\nResponse count: {len(response.data)} | Data: {response.data}")

        self.assertEqual(
            len(response.data),
            3,
        )
        

    def test_provider_list_api(self):
        response = self.client.get(
            reverse("provider-list")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            2,
        )

    # ========================================================
    # Create
    # ========================================================

    def test_patient_can_create_appointment_request(self):
        response = self.create_appointment()

        self.assertEqual(
            response.data["status"],
            Appointment.Status.PENDING,
        )

        self.assertEqual(
            response.data["version"],
            1,
        )

        self.assertEqual(
            response.data["patient_name"],
            self.patient.name,
        )

        self.assertEqual(
            response.data["provider_name"],
            self.provider.name,
        )

    def test_create_appointment_validates_past_time(self):
        payload = self.appointment_payload(
            scheduled_at=(
                timezone.now()
                - timedelta(hours=1)
            )
        )

        response = self.client.post(
            reverse("appointment-list-create"),
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_create_appointment_rejects_unknown_patient(self):
        payload = self.appointment_payload(
            patient_id=99999,
        )

        response = self.client.post(
            reverse("appointment-list-create"),
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # List / detail
    # ========================================================

    def test_appointment_list_api(self):
        self.create_appointment()

        response = self.client.get(
            reverse("appointment-list-create")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

    def test_patient_filter(self):
        self.create_appointment()

        other_time = (
            self.start_time
            + timedelta(hours=2)
        )

        response = self.client.post(
            reverse("appointment-list-create"),
            self.appointment_payload(
                patient_id=self.second_patient.id,
                scheduled_at=other_time,
            ),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        response = self.client.get(
            reverse("appointment-list-create"),
            {
                "patient_id": self.patient.id,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["patient"],
            self.patient.id,
        )

    def test_provider_filter(self):
        self.create_appointment()

        response = self.client.get(
            reverse("appointment-list-create"),
            {
                "provider_id": self.provider.id,
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

    def test_appointment_detail_api(self):
        create_response = self.create_appointment()

        appointment_id = create_response.data["id"]

        response = self.client.get(
            reverse(
                "appointment-detail",
                kwargs={
                    "pk": appointment_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["id"],
            appointment_id,
        )

    # ========================================================
    # Confirm
    # ========================================================

    def test_provider_can_confirm_through_api(self):
        create_response = self.create_appointment()

        appointment_id = create_response.data["id"]
        version = create_response.data["version"]

        response = self.client.post(
            reverse(
                "appointment-confirm",
                kwargs={
                    "pk": appointment_id,
                },
            ),
            {
                "provider_id": self.provider.id,
                "expected_version": version,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["status"],
            Appointment.Status.CONFIRMED,
        )

        self.assertEqual(
            response.data["version"],
            2,
        )

    # ========================================================
    # Problem 1
    # ========================================================

    def test_stale_version_returns_409(self):
        create_response = self.create_appointment()

        appointment_id = create_response.data["id"]

        # Provider changes the appointment first.
        response = self.client.post(
            reverse(
                "appointment-reschedule",
                kwargs={
                    "pk": appointment_id,
                },
            ),
            {
                "provider_id": self.provider.id,
                "new_scheduled_at": (
                    self.start_time
                    + timedelta(hours=2)
                ).isoformat(),
                "expected_version": 1,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # Patient still has stale version 1.
        response = self.client.post(
            reverse(
                "appointment-cancel",
                kwargs={
                    "pk": appointment_id,
                },
            ),
            {
                "patient_id": self.patient.id,
                "expected_version": 1,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

        self.assertEqual(
            response.data["error"],
            "appointment_version_conflict",
        )

    # ========================================================
    # Cancel
    # ========================================================

    def test_pending_appointment_cannot_be_cancelled(self):
        create_response = self.create_appointment()

        appointment_id = create_response.data["id"]

        response = self.client.post(
            reverse(
                "appointment-cancel",
                kwargs={
                    "pk": appointment_id,
                },
            ),
            {
                "patient_id": self.patient.id,
                "expected_version": 1,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        appointment = Appointment.objects.get(
            pk=appointment_id
        )

        self.assertEqual(
            appointment.status,
            Appointment.Status.PENDING,
        )

    def test_patient_can_cancel_confirmed_appointment(self):
        create_response = self.create_appointment()

        appointment_id = create_response.data["id"]

        confirm_response = self.client.post(
            reverse(
                "appointment-confirm",
                kwargs={
                    "pk": appointment_id,
                },
            ),
            {
                "provider_id": self.provider.id,
                "expected_version": 1,
            },
            format="json",
        )

        self.assertEqual(
            confirm_response.status_code,
            status.HTTP_200_OK,
        )

        response = self.client.post(
            reverse(
                "appointment-cancel",
                kwargs={
                    "pk": appointment_id,
                },
            ),
            {
                "patient_id": self.patient.id,
                "expected_version": 2,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["status"],
            Appointment.Status.CANCELLED,
        )

    # ========================================================
    # Reschedule
    # ========================================================

    def test_provider_can_reschedule_through_api(self):
        create_response = self.create_appointment()

        appointment_id = create_response.data["id"]

        new_time = (
            self.start_time
            + timedelta(hours=3)
        )

        response = self.client.post(
            reverse(
                "appointment-reschedule",
                kwargs={
                    "pk": appointment_id,
                },
            ),
            {
                "provider_id": self.provider.id,
                "new_scheduled_at": new_time.isoformat(),
                "expected_version": 1,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["version"],
            2,
        )

        appointment = Appointment.objects.get(
            pk=appointment_id
        )

        self.assertEqual(
            appointment.scheduled_at,
            new_time,
        )

    # ========================================================
    # Problem 2
    # ========================================================

    def test_history_api_returns_audit_trail(self):
        create_response = self.create_appointment()

        appointment_id = create_response.data["id"]

        self.client.post(
            reverse(
                "appointment-reschedule",
                kwargs={
                    "pk": appointment_id,
                },
            ),
            {
                "provider_id": self.provider.id,
                "new_scheduled_at": (
                    self.start_time
                    + timedelta(hours=2)
                ).isoformat(),
                "expected_version": 1,
            },
            format="json",
        )

        response = self.client.get(
            reverse(
                "appointment-history",
                kwargs={
                    "pk": appointment_id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            2,
        )

        self.assertEqual(
            response.data[0]["action"],
            AppointmentHistory.Action.CREATED,
        )

        self.assertEqual(
            response.data[1]["action"],
            AppointmentHistory.Action.RESCHEDULED,
        )

    # ========================================================
    # Problem 3
    # ========================================================

    def test_confirmation_creates_notification(self):
        create_response = self.create_appointment()

        appointment_id = create_response.data["id"]

        response = self.client.post(
            reverse(
                "appointment-confirm",
                kwargs={
                    "pk": appointment_id,
                },
            ),
            {
                "provider_id": self.provider.id,
                "expected_version": 1,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        notification = (
            NotificationOutbox.objects.get(
                appointment_id=appointment_id
            )
        )

        self.assertEqual(
            notification.recipient,
            self.patient.email,
        )

        self.assertEqual(
            notification.channel,
            NotificationOutbox.Channel.EMAIL,
        )

    def test_notification_api(self):
        create_response = self.create_appointment()

        appointment_id = create_response.data["id"]

        self.client.post(
            reverse(
                "appointment-confirm",
                kwargs={
                    "pk": appointment_id,
                },
            ),
            {
                "provider_id": self.provider.id,
                "expected_version": 1,
            },
            format="json",
        )

        response = self.client.get(
            reverse("notification-list")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

    # ========================================================
    # Problem 4
    # ========================================================

    def test_overlapping_confirmation_returns_409(self):
        first_response = self.create_appointment()

        first_id = first_response.data["id"]

        response = self.client.post(
            reverse(
                "appointment-confirm",
                kwargs={
                    "pk": first_id,
                },
            ),
            {
                "provider_id": self.provider.id,
                "expected_version": 1,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        second_time = (
            self.start_time
            + timedelta(minutes=30)
        )

        second_response = self.client.post(
            reverse("appointment-list-create"),
            self.appointment_payload(
                patient_id=self.second_patient.id,
                scheduled_at=second_time,
            ),
            format="json",
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_201_CREATED,
        )

        second_id = second_response.data["id"]

        response = self.client.post(
            reverse(
                "appointment-confirm",
                kwargs={
                    "pk": second_id,
                },
            ),
            {
                "provider_id": self.provider.id,
                "expected_version": 1,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

        self.assertEqual(
            response.data["error"],
            "appointment_overlap",
        )

        second = Appointment.objects.get(
            pk=second_id
        )

        self.assertEqual(
            second.status,
            Appointment.Status.PENDING,
        )