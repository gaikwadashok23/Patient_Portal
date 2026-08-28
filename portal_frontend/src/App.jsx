import { useEffect, useState } from "react";
import AppointmentRequestModal from "./components/AppointmentRequestModal";
import AppointmentDetail from "./components/AppointmentDetail";

import ProviderAppointmentDetail
    from "./components/ProviderAppointmentDetail";

import {
    getAppointments,
    getPatients,
    getProviders,
} from "./api/api";


function formatDateTime(value) {
    if (!value) {
        return "—";
    }

    const date = new Date(value);

    return date.toLocaleString("en-IN", {
        weekday: "short",
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}


function statusClass(status) {
    return `status-badge status-${status}`;
}


function App() {
    const [role, setRole] = useState("patient");

    const [patients, setPatients] = useState([]);
    const [providers, setProviders] = useState([]);

    const [appointments, setAppointments] = useState([]);

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const [showAppointmentModal, setShowAppointmentModal] = useState(false);

    const [selectedAppointmentId, setSelectedAppointmentId] = useState(null);


    /*
     * For this assignment authentication is intentionally
     * omitted.
     *
     * We simulate the currently selected user using the
     * first seeded patient/provider.
     */
    const currentPatient = patients[0];
    const currentProvider = providers[0];


    useEffect(() => {
        async function loadReferenceData() {
            try {
                setLoading(true);
                setError("");

                const [
                    patientsData,
                    providersData,
                ] = await Promise.all([
                    getPatients(),
                    getProviders(),
                ]);

                setPatients(
                    Array.isArray(patientsData)
                        ? patientsData
                        : patientsData.results || []
                );

                setProviders(
                    Array.isArray(providersData)
                        ? providersData
                        : providersData.results || []
                );
            } catch (err) {
                console.error(err);

                setError(
                    "Unable to connect to the healthcare service."
                );
            } finally {
                setLoading(false);
            }
        }

        loadReferenceData();
    }, []);


    /*
     * Reusable appointment loader.
     *
     * Pulled out of useEffect so it can also be called
     * after a successful appointment request (see modal
     * onSuccess below) to refresh the list immediately.
     */
    async function loadAppointments() {
        const currentUser =
            role === "patient"
                ? currentPatient
                : currentProvider;

        if (!currentUser) {
            return;
        }

        try {
            setLoading(true);
            setError("");

            const params =
                role === "patient"
                    ? {
                          patient_id:
                              currentUser.id,
                      }
                    : {
                          provider_id:
                              currentUser.id,
                      };

            const data =
                await getAppointments(params);

            setAppointments(
                Array.isArray(data)
                    ? data
                    : data.results || []
            );
        } catch (err) {
            console.error(err);

            setError(
                "Unable to load appointments."
            );
        } finally {
            setLoading(false);
        }
    }


    useEffect(() => {
        loadAppointments();
    }, [
        role,
        currentPatient,
        currentProvider,
    ]);


    const upcomingAppointments =
        appointments.filter(
            (appointment) =>
                appointment.status !== "cancelled"
        );


    const pendingCount =
        appointments.filter(
            (appointment) =>
                appointment.status === "pending"
        ).length;


    const confirmedCount =
        appointments.filter(
            (appointment) =>
                appointment.status === "confirmed"
        ).length;


    return (
        <div className="app-shell">

            {/* ================= SIDEBAR ================= */}

            <aside className="sidebar">

                <div className="brand">

                    <div className="brand-mark">
                        +
                    </div>

                    <div>
                        <div className="brand-name">
                            CarePortal
                        </div>

                        <div className="brand-subtitle">
                            Patient Health Platform
                        </div>
                    </div>

                </div>


                <nav className="sidebar-nav">

                    <button className="nav-item active">
                        <span className="nav-icon">
                            ⌂
                        </span>

                        Dashboard
                    </button>


                    <button className="nav-item">
                        <span className="nav-icon">
                            ▣
                        </span>

                        Appointments
                    </button>


                    <button className="nav-item">
                        <span className="nav-icon">
                            ◷
                        </span>

                        History
                    </button>

                </nav>


                <div className="sidebar-footer">

                    <div className="secure-indicator">

                        <span className="secure-dot"></span>

                        Secure healthcare portal

                    </div>

                </div>

            </aside>


            {/* ================= MAIN ================= */}

            <main className="main-content">

                <header className="topbar">

                    <div>

                        <div className="breadcrumb">
                            CarePortal / Dashboard
                        </div>

                        <h1>
                            {role === "patient"
                                ? "Patient Dashboard"
                                : "Provider Dashboard"}
                        </h1>

                    </div>


                    <div className="topbar-actions">

                        <div className="role-switcher">

                            <span className="role-label">
                                View as
                            </span>


                            <button
                                className={
                                    role === "patient"
                                        ? "role-button selected"
                                        : "role-button"
                                }
                                onClick={() =>
                                    setRole("patient")
                                }
                            >
                                Patient
                            </button>


                            <button
                                className={
                                    role === "provider"
                                        ? "role-button selected"
                                        : "role-button"
                                }
                                onClick={() =>
                                    setRole("provider")
                                }
                            >
                                Provider
                            </button>

                        </div>


                        <div className="profile">

                            <div className="profile-avatar">
                                {role === "patient"
                                    ? "AG"
                                    : "DR"}
                            </div>


                            <div className="profile-info">

                                <strong>
                                    {role === "patient"
                                        ? currentPatient?.name ||
                                          "Patient"
                                        : currentProvider?.name ||
                                          "Provider"}
                                </strong>

                                <span>
                                    {role === "patient"
                                        ? "Patient"
                                        : "Healthcare Provider"}
                                </span>

                            </div>

                        </div>

                    </div>

                </header>


                {selectedAppointmentId ? (

                    role === "patient" ? (

                        <AppointmentDetail
                            appointmentId={
                                selectedAppointmentId
                            }
                            onBack={() =>
                                setSelectedAppointmentId(null)
                            }
                            onUpdated={
                                loadAppointments
                            }
                        />

                    ) : (

                        <ProviderAppointmentDetail
                            appointmentId={
                                selectedAppointmentId
                            }
                            onBack={() =>
                                setSelectedAppointmentId(null)
                            }
                            onUpdated={
                                loadAppointments
                            }
                        />

                    )

                ) : (

                <section className="dashboard-content">

                    {/* ================= WELCOME ================= */}

                    <div className="welcome-card">

                        <div>

                            <span className="eyebrow">
                                {role === "patient"
                                    ? "YOUR HEALTHCARE"
                                    : "PROVIDER WORKSPACE"}
                            </span>


                            <h2>
                                {role === "patient"
                                    ? `Welcome back, ${
                                          currentPatient?.name ||
                                          "Patient"
                                      }`
                                    : `Good afternoon, ${
                                          currentProvider?.name ||
                                          "Provider"
                                      }`}
                            </h2>


                            <p>
                                {role === "patient"
                                    ? "Manage your appointments and stay connected with your care team."
                                    : "Review appointment requests and manage your patient schedule."}
                            </p>

                        </div>


                        <div className="welcome-symbol">
                            +
                        </div>

                    </div>


                    {/* ================= ERROR ================= */}

                    {error && (
                        <div className="error-banner">
                            {error}
                        </div>
                    )}


                    {/* ================= STATS ================= */}

                    <div className="stats-grid">

                        <div className="stat-card">

                            <span className="stat-label">
                                Upcoming
                            </span>

                            <strong className="stat-value">
                                {upcomingAppointments.length}
                            </strong>

                            <span className="stat-description">
                                appointments
                            </span>

                        </div>


                        <div className="stat-card">

                            <span className="stat-label">
                                Pending
                            </span>

                            <strong className="stat-value">
                                {pendingCount}
                            </strong>

                            <span className="stat-description">
                                awaiting confirmation
                            </span>

                        </div>


                        <div className="stat-card">

                            <span className="stat-label">
                                Confirmed
                            </span>

                            <strong className="stat-value">
                                {confirmedCount}
                            </strong>

                            <span className="stat-description">
                                scheduled visits
                            </span>

                        </div>

                    </div>


                    {/* ================= APPOINTMENTS ================= */}

                    <div className="section-header">

                        <div>

                            <h3>
                                Upcoming appointments
                            </h3>

                            <p>
                                {role === "patient"
                                    ? "Your scheduled visits"
                                    : "Appointments assigned to you"}
                            </p>

                        </div>


                        {role === "patient" && (
                            <button
                                className="primary-button"
                                onClick={() =>
                                    setShowAppointmentModal(true)
                                }
                            >
                                + Request appointment
                            </button>
                        )}

                    </div>


                    {loading ? (

                        <div className="appointment-placeholder">

                            <div className="loading-spinner"></div>

                            <h3>
                                Loading appointments...
                            </h3>

                        </div>

                    ) : upcomingAppointments.length === 0 ? (

                        <div className="appointment-placeholder">

                            <div className="empty-icon">
                                ✓
                            </div>

                            <h3>
                                No upcoming appointments
                            </h3>

                            <p>
                                Your scheduled visits will
                                appear here.
                            </p>

                        </div>

                    ) : (

                        <div className="appointments-list">

                            {upcomingAppointments.map(
                                (appointment) => (

                                    <div
                                        className="appointment-card"
                                        key={
                                            appointment.id
                                        }
                                        onClick={() =>
                                            setSelectedAppointmentId(
                                                appointment.id
                                            )
                                        }
                                    >

                                        <div className="appointment-date">

                                            <div className="appointment-day">
                                                {new Date(
                                                    appointment.scheduled_at
                                                ).getDate()}
                                            </div>

                                            <div className="appointment-month">
                                                {new Date(
                                                    appointment.scheduled_at
                                                ).toLocaleString(
                                                    "en-IN",
                                                    {
                                                        month: "short",
                                                    }
                                                )}
                                            </div>

                                        </div>


                                        <div className="appointment-main">

                                            <div className="appointment-title">

                                                <h3>
                                                    {appointment.appointment_type_display ||
                                                        appointment.appointment_type}
                                                </h3>

                                                <span
                                                    className={statusClass(
                                                        appointment.status
                                                    )}
                                                >
                                                    {appointment.status}
                                                </span>

                                            </div>


                                            <p>
                                                {role ===
                                                "patient"
                                                    ? `Provider: ${
                                                          appointment.provider_name ||
                                                          "Healthcare Provider"
                                                      }`
                                                    : `Patient: ${
                                                          appointment.patient_name ||
                                                          "Patient"
                                                      }`}
                                            </p>


                                            <div className="appointment-meta">

                                                <span>
                                                    🕐{" "}
                                                    {formatDateTime(
                                                        appointment.scheduled_at
                                                    )}
                                                </span>

                                                <span>
                                                    •{" "}
                                                    {
                                                        appointment.duration_minutes
                                                    }{" "}
                                                    min
                                                </span>

                                            </div>

                                        </div>


                                        <div className="appointment-arrow">
                                            →
                                        </div>

                                    </div>

                                )
                            )}

                        </div>

                    )}

                </section>

                )}

            </main>


            {/* ================= APPOINTMENT REQUEST MODAL ================= */}

            {showAppointmentModal &&
                role === "patient" &&
                currentPatient && (
                    <AppointmentRequestModal
                        patient={currentPatient}
                        onClose={() =>
                            setShowAppointmentModal(false)
                        }
                        onSuccess={async () => {
                            setShowAppointmentModal(false);

                            await loadAppointments();
                        }}
                    />
                )}

        </div>
    );
}


export default App;
