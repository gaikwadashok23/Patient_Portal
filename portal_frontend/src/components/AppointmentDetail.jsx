import { useEffect, useState } from "react";

import {
    getAppointment,
    getAppointmentHistory,
    cancelAppointment,
} from "../api/api";


/* ============================================================
   DATE FORMATTER
============================================================ */

function formatDateTime(value) {
    if (!value) {
        return "—";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "—";
    }

    return date.toLocaleString("en-IN", {
        weekday: "long",
        day: "2-digit",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}


/* ============================================================
   HISTORY ACTION FORMATTER
============================================================ */

function formatAction(action) {
    if (!action) {
        return "";
    }

    return action
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) =>
            letter.toUpperCase()
        );
}


/* ============================================================
   COMPONENT
============================================================ */

export default function AppointmentDetail({
    appointmentId,
    onBack,
    onUpdated,
}) {

    const [appointment, setAppointment] =
        useState(null);

    const [history, setHistory] =
        useState([]);

    const [loading, setLoading] =
        useState(true);

    const [cancelling, setCancelling] =
        useState(false);

    const [error, setError] =
        useState("");

    const [success, setSuccess] =
        useState("");


    /* ========================================================
       LOAD APPOINTMENT + HISTORY
    ======================================================== */

    async function loadData({
        showLoading = true,
        clearMessages = true,
    } = {}) {

        if (!appointmentId) {
            setError(
                "Appointment ID is missing."
            );

            setLoading(false);

            return;
        }

        try {

            if (showLoading) {
                setLoading(true);
            }

            if (clearMessages) {
                setError("");
            }

            const [
                appointmentData,
                historyData,
            ] = await Promise.all([
                getAppointment(
                    appointmentId
                ),

                getAppointmentHistory(
                    appointmentId
                ),
            ]);


            /*
             * IMPORTANT:
             *
             * Always replace the appointment with
             * the latest backend representation.
             *
             * This is especially important after
             * a 409 version conflict.
             */

            setAppointment(
                appointmentData
            );


            setHistory(
                Array.isArray(historyData)
                    ? historyData
                    : historyData?.results || []
            );

        } catch (error) {

            console.error(
                "LOAD APPOINTMENT ERROR:",
                error
            );

            setError(
                error.message ||
                "Unable to load appointment."
            );

        } finally {

            if (showLoading) {
                setLoading(false);
            }
        }
    }


    /* ========================================================
       INITIAL LOAD
    ======================================================== */

    useEffect(() => {

        loadData();

    }, [appointmentId]);


    /* ========================================================
       CANCEL APPOINTMENT
    ======================================================== */

    async function handleCancel() {

        if (!appointment) {
            return;
        }


        /* ----------------------------------------------------
           STATUS CHECK
        ---------------------------------------------------- */

        if (
            appointment.status !==
            "confirmed"
        ) {

            setError(
                "Only confirmed appointments can be cancelled."
            );

            return;
        }


        /* ----------------------------------------------------
           REAL PATIENT ID CHECK
        ---------------------------------------------------- */

        if (!appointment.patient) {

            setError(
                "Patient information is missing. Please refresh the appointment."
            );

            return;
        }


        /* ----------------------------------------------------
           VERSION CHECK
        ---------------------------------------------------- */

        if (
            appointment.version === undefined ||
            appointment.version === null
        ) {

            setError(
                "Appointment version is missing. Please refresh the appointment."
            );

            return;
        }


        /* ----------------------------------------------------
           CONFIRMATION
        ---------------------------------------------------- */

        const shouldCancel =
            window.confirm(
                "Are you sure you want to cancel this appointment?"
            );


        if (!shouldCancel) {
            return;
        }


        try {

            setCancelling(true);

            setError("");

            setSuccess("");


            /*
             * IMPORTANT:
             *
             * Pass the complete REAL appointment object.
             *
             * api.js extracts:
             *
             * appointment.id
             * appointment.patient
             * appointment.version
             *
             * and sends:
             *
             * {
             *     patient_id: appointment.patient,
             *     expected_version: appointment.version
             * }
             */

            const updated =
                await cancelAppointment(
                    appointment
                );


            /*
             * Update immediately with backend response.
             */

            setAppointment(updated);


            setSuccess(
                "Appointment cancelled successfully."
            );


            /*
             * Reload history and latest appointment.
             */

            await loadData({
                showLoading: false,
                clearMessages: false,
            });


            if (onUpdated) {
                onUpdated();
            }

        } catch (error) {

            console.error(
                "CANCEL APPOINTMENT ERROR:",
                error
            );


            /* =================================================
               PROBLEM 1
               
               Provider changed appointment while the patient
               was looking at an older version.
            ================================================= */

            if (
                error.status === 409 ||
                error.data?.error ===
                    "appointment_version_conflict"
            ) {

                /*
                 * IMPORTANT:
                 *
                 * The cancellation DID NOT happen.
                 *
                 * Backend rejected the stale request.
                 */

                setSuccess("");


                setError(
                    "Appointment updated. The provider changed this appointment while you were viewing it. Your cancellation was not applied. We have refreshed the latest appointment details."
                );


                /*
                 * Load the latest appointment.
                 *
                 * This will update:
                 *
                 * - scheduled_at
                 * - version
                 * - status
                 * - provider information
                 */

                await loadData({
                    showLoading: false,
                    clearMessages: false,
                });


                return;
            }


            /* =================================================
               NORMAL API ERROR
            ================================================= */

            setError(
                error.message ||
                "Unable to cancel appointment."
            );

        } finally {

            setCancelling(false);
        }
    }


    /* ========================================================
       LOADING STATE
    ======================================================== */

    if (loading) {

        return (
            <div className="detail-page">

                <button
                    className="back-button"
                    onClick={onBack}
                >
                    ← Back to appointments
                </button>


                <div className="detail-loading">
                    Loading appointment...
                </div>

            </div>
        );
    }


    /* ========================================================
       APPOINTMENT NOT FOUND
    ======================================================== */

    if (!appointment) {

        return (
            <div className="detail-page">

                <button
                    className="back-button"
                    onClick={onBack}
                >
                    ← Back
                </button>


                <div
                    className="detail-error"
                    role="alert"
                >
                    {error ||
                        "Appointment not found."}
                </div>

            </div>
        );
    }


    /* ========================================================
       UI
    ======================================================== */

    return (
        <div className="detail-page">


            {/* ==================================================
                HEADER
            ================================================== */}

            <div className="detail-header">

                <button
                    className="back-button"
                    onClick={onBack}
                    disabled={cancelling}
                >
                    ← Back to appointments
                </button>


                <span
                    className={`status-badge status-${appointment.status}`}
                >
                    {
                        appointment.status_display ||
                        appointment.status
                    }
                </span>

            </div>


            {/* ==================================================
                ERROR / CONFLICT MESSAGE
            ================================================== */}

            {error && (

                <div
                    className="error-banner"
                    role="alert"
                >

                    <strong>
                        Appointment updated
                    </strong>

                    <p>
                        {error}
                    </p>

                </div>

            )}


            {/* ==================================================
                SUCCESS MESSAGE
            ================================================== */}

            {success && (

                <div
                    className="success-banner"
                    role="status"
                >
                    {success}
                </div>

            )}


            {/* ==================================================
                APPOINTMENT CARD
            ================================================== */}

            <div className="detail-card">


                {/* ----------------------------------------------
                    CARD HEADER
                ---------------------------------------------- */}

                <div className="detail-card-header">

                    <div>

                        <span className="eyebrow">
                            PATIENT APPOINTMENT
                        </span>


                        <h2>
                            {
                                appointment.appointment_type_display ||
                                appointment.appointment_type ||
                                "Appointment"
                            }
                        </h2>

                    </div>


                    <div className="appointment-id">
                        #{appointment.id}
                    </div>

                </div>


                {/* ----------------------------------------------
                    APPOINTMENT DETAILS
                ---------------------------------------------- */}

                <div className="detail-grid">


                    {/* DATE */}

                    <div className="detail-item">

                        <span>
                            Date & time
                        </span>

                        <strong>
                            {formatDateTime(
                                appointment.scheduled_at
                            )}
                        </strong>

                    </div>


                    {/* DURATION */}

                    <div className="detail-item">

                        <span>
                            Duration
                        </span>

                        <strong>
                            {
                                appointment.duration_minutes ??
                                "—"
                            }{" "}
                            minutes
                        </strong>

                    </div>


                    {/* PROVIDER */}

                    <div className="detail-item">

                        <span>
                            Provider
                        </span>

                        <strong>
                            {
                                appointment.provider_name ||
                                "—"
                            }
                        </strong>

                    </div>


                    {/* PATIENT */}

                    <div className="detail-item">

                        <span>
                            Patient
                        </span>

                        <strong>
                            {
                                appointment.patient_name ||
                                "—"
                            }
                        </strong>

                    </div>

                </div>


                {/* ----------------------------------------------
                    REASON
                ---------------------------------------------- */}

                <div className="reason-section">

                    <span>
                        Reason for visit
                    </span>

                    <p>
                        {
                            appointment.reason ||
                            "No reason provided."
                        }
                    </p>

                </div>


                {/* =================================================
                    CONFIRMED
                ================================================= */}

                {appointment.status ===
                    "confirmed" && (

                    <div className="detail-actions">

                        <button
                            className="danger-button"
                            disabled={cancelling}
                            onClick={
                                handleCancel
                            }
                        >

                            {cancelling
                                ? "Cancelling..."
                                : "Cancel appointment"}

                        </button>

                    </div>

                )}


                {/* =================================================
                    PENDING
                ================================================= */}

                {appointment.status ===
                    "pending" && (

                    <div className="pending-notice">

                        <strong>
                            Awaiting provider confirmation
                        </strong>

                        <p>
                            Pending appointment requests
                            cannot be cancelled.
                        </p>

                    </div>

                )}


                {/* =================================================
                    CANCELLED
                ================================================= */}

                {appointment.status ===
                    "cancelled" && (

                    <div className="cancelled-notice">

                        This appointment has been
                        cancelled.

                    </div>

                )}

            </div>


            {/* ====================================================
                AUDIT HISTORY
            ==================================================== */}

            <div className="history-card">


                <div className="history-header">

                    <span className="eyebrow">
                        AUDIT TRAIL
                    </span>

                    <h2>
                        Appointment history
                    </h2>

                </div>


                {history.length === 0 ? (

                    <p className="history-empty">
                        No history available.
                    </p>

                ) : (

                    <div className="history-list">

                        {history.map((item) => (

                            <div
                                className="history-item"
                                key={item.id}
                            >

                                <div
                                    className="history-dot"
                                />


                                <div
                                    className="history-content"
                                >


                                    {/* HISTORY TITLE */}

                                    <div
                                        className="history-title"
                                    >

                                        <strong>
                                            {formatAction(
                                                item.action
                                            )}
                                        </strong>


                                        <span>
                                            {
                                                item.actor_name ||
                                                "System"
                                            }
                                        </span>

                                    </div>


                                    {/* HISTORY TIME */}

                                    <div
                                        className="history-time"
                                    >
                                        {formatDateTime(
                                            item.created_at
                                        )}
                                    </div>


                                    {/* HISTORY CHANGES */}

                                    <div
                                        className="history-change"
                                    >


                                        {/* STATUS CHANGE */}

                                        {item.old_status &&
                                            item.new_status &&
                                            item.old_status !==
                                                item.new_status && (

                                            <span>

                                                Status:{" "}

                                                {
                                                    item.old_status
                                                }

                                                {" → "}

                                                {
                                                    item.new_status
                                                }

                                            </span>

                                        )}


                                        {/* TIME CHANGE */}

                                        {item.old_scheduled_at &&
                                            item.new_scheduled_at &&
                                            item.old_scheduled_at !==
                                                item.new_scheduled_at && (

                                            <span>

                                                Time:{" "}

                                                {formatDateTime(
                                                    item.old_scheduled_at
                                                )}

                                                {" → "}

                                                {formatDateTime(
                                                    item.new_scheduled_at
                                                )}

                                            </span>

                                        )}

                                    </div>

                                </div>

                            </div>

                        ))}

                    </div>

                )}

            </div>

        </div>
    );
}
