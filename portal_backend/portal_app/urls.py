from django.urls import path

from .views import (
    AppointmentCancelAPIView,
    AppointmentConfirmAPIView,
    AppointmentDetailAPIView,
    AppointmentHistoryAPIView,
    AppointmentListCreateAPIView,
    AppointmentRescheduleAPIView,
    NotificationOutboxAPIView,
    PatientListAPIView,
    ProviderListAPIView,
)


urlpatterns = [
    # --------------------------------------------------------
    # Patients / Providers
    # --------------------------------------------------------

    path(
        "patients/",
        PatientListAPIView.as_view(),
        name="patient-list",
    ),

    path(
        "providers/",
        ProviderListAPIView.as_view(),
        name="provider-list",
    ),

    # --------------------------------------------------------
    # Appointments
    # --------------------------------------------------------

    path(
        "appointments/",
        AppointmentListCreateAPIView.as_view(),
        name="appointment-list-create",
    ),

    path(
        "appointments/<int:pk>/",
        AppointmentDetailAPIView.as_view(),
        name="appointment-detail",
    ),

    # --------------------------------------------------------
    # Appointment commands
    # --------------------------------------------------------

    path(
        "appointments/<int:pk>/confirm/",
        AppointmentConfirmAPIView.as_view(),
        name="appointment-confirm",
    ),

    path(
        "appointments/<int:pk>/reschedule/",
        AppointmentRescheduleAPIView.as_view(),
        name="appointment-reschedule",
    ),

    path(
        "appointments/<int:pk>/cancel/",
        AppointmentCancelAPIView.as_view(),
        name="appointment-cancel",
    ),

    # --------------------------------------------------------
    # Problem 2 - Audit history
    # --------------------------------------------------------

    path(
        "appointments/<int:pk>/history/",
        AppointmentHistoryAPIView.as_view(),
        name="appointment-history",
    ),

    # --------------------------------------------------------
    # Problem 3 - Notification outbox
    # --------------------------------------------------------

    path(
        "notifications/",
        NotificationOutboxAPIView.as_view(),
        name="notification-list",
    ),
]