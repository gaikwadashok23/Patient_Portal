const API_BASE_URL = "http://127.0.0.1:8000/api";

/* ============================================================
   API ERROR
============================================================ */

class APIError extends Error {
    constructor(message, status, data) {
        super(message);

        this.name = "APIError";
        this.status = status;
        this.data = data;
    }
}


/* ============================================================
   GENERIC REQUEST
============================================================ */

async function request(endpoint, options = {}) {
    const response = await fetch(
        `${API_BASE_URL}${endpoint}`,
        {
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
                ...(options.headers || {}),
            },
            ...options,
        }
    );

    let data = null;

    const contentType =
        response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
        try {
            data = await response.json();
        } catch {
            data = null;
        }
    } else {
        try {
            const text = await response.text();
            data = text || null;
        } catch {
            data = null;
        }
    }


    /* ========================================================
       ERROR HANDLING
    ======================================================== */

    if (!response.ok) {
        let message =
            "Something went wrong. Please try again.";

        if (data?.detail) {
            message = data.detail;
        } else if (
            data &&
            typeof data === "object"
        ) {
            const messages = [];

            Object.entries(data).forEach(
                ([field, value]) => {

                    if (Array.isArray(value)) {
                        value.forEach((item) => {
                            messages.push(
                                `${field}: ${item}`
                            );
                        });
                    } else if (
                        typeof value === "string"
                    ) {
                        messages.push(
                            `${field}: ${value}`
                        );
                    } else {
                        messages.push(
                            `${field}: ${JSON.stringify(value)}`
                        );
                    }
                }
            );

            if (messages.length > 0) {
                message = messages.join("\n");
            }
        }

        throw new APIError(
            message,
            response.status,
            data
        );
    }

    return data;
}


/* ============================================================
   PATIENTS
============================================================ */

export async function getPatients() {
    return request("/patients/");
}


/* ============================================================
   PROVIDERS
============================================================ */

export async function getProviders() {
    return request("/providers/");
}


/* ============================================================
   APPOINTMENTS - LIST
============================================================ */

export async function getAppointments(params = {}) {
    const searchParams = new URLSearchParams();

    Object.entries(params).forEach(
        ([key, value]) => {

            if (
                value !== undefined &&
                value !== null &&
                value !== ""
            ) {
                searchParams.append(
                    key,
                    value
                );
            }
        }
    );

    const query =
        searchParams.toString();

    return request(
        query
            ? `/appointments/?${query}`
            : "/appointments/"
    );
}


/* ============================================================
   APPOINTMENT - DETAIL
============================================================ */

export async function getAppointment(id) {

    if (!id) {
        throw new Error(
            "Appointment ID is required."
        );
    }

    return request(
        `/appointments/${id}/`
    );
}


/* ============================================================
   CREATE APPOINTMENT
============================================================ */

export async function createAppointment(payload) {

    if (!payload) {
        throw new Error(
            "Appointment data is required."
        );
    }

    return request(
        "/appointments/",
        {
            method: "POST",

            body: JSON.stringify(payload),
        }
    );
}


/* ============================================================
   CONFIRM APPOINTMENT
============================================================ */

/**
 * Provider confirms a pending appointment.
 *
 * Backend:
 *
 * POST /appointments/{id}/confirm/
 *
 * Body:
 *
 * {
 *     provider_id: 1,
 *     expected_version: 1
 * }
 *
 * IMPORTANT:
 * provider_id comes from appointment.provider.
 *
 * No hardcoded provider ID.
 */

export async function confirmAppointment(
    appointment
) {

    if (!appointment?.id) {
        throw new Error(
            "Appointment ID is required."
        );
    }

    if (!appointment?.provider) {
        throw new Error(
            "Provider ID is required."
        );
    }

    if (
        appointment.version === undefined ||
        appointment.version === null
    ) {
        throw new Error(
            "Appointment version is required."
        );
    }

    return request(
        `/appointments/${appointment.id}/confirm/`,
        {
            method: "POST",

            body: JSON.stringify({
                provider_id:
                    appointment.provider,

                expected_version:
                    appointment.version,
            }),
        }
    );
}


/* ============================================================
   RESCHEDULE APPOINTMENT
============================================================ */

/**
 * Provider reschedules appointment.
 *
 * Pending and confirmed appointments may be
 * rescheduled according to backend business rules.
 *
 * Backend:
 *
 * POST /appointments/{id}/reschedule/
 *
 * Body:
 *
 * {
 *     provider_id: 1,
 *     new_scheduled_at: "...",
 *     expected_version: 1
 * }
 *
 * IMPORTANT:
 *
 * provider_id:
 *     appointment.provider
 *
 * expected_version:
 *     appointment.version
 *
 * No hardcoded IDs.
 */

export async function rescheduleAppointment(
    appointment,
    newScheduledAt
) {

    if (!appointment?.id) {
        throw new Error(
            "Appointment ID is required."
        );
    }

    if (!appointment?.provider) {
        throw new Error(
            "Provider ID is required."
        );
    }

    if (!newScheduledAt) {
        throw new Error(
            "New appointment date/time is required."
        );
    }

    if (
        appointment.version === undefined ||
        appointment.version === null
    ) {
        throw new Error(
            "Appointment version is required."
        );
    }

    return request(
        `/appointments/${appointment.id}/reschedule/`,
        {
            method: "POST",

            body: JSON.stringify({
                provider_id:
                    appointment.provider,

                new_scheduled_at:
                    newScheduledAt,

                expected_version:
                    appointment.version,
            }),
        }
    );
}


/* ============================================================
   CANCEL APPOINTMENT
============================================================ */

/**
 * Patient cancels a confirmed appointment.
 *
 * Backend:
 *
 * POST /appointments/{id}/cancel/
 *
 * Body:
 *
 * {
 *     patient_id: 1,
 *     expected_version: 1
 * }
 *
 * IMPORTANT:
 *
 * patient_id:
 *     appointment.patient
 *
 * expected_version:
 *     appointment.version
 *
 * No hardcoded IDs.
 */

export async function cancelAppointment(
    appointment
) {

    if (!appointment?.id) {
        throw new Error(
            "Appointment ID is required."
        );
    }

    if (!appointment?.patient) {
        throw new Error(
            "Patient ID is required."
        );
    }

    if (
        appointment.version === undefined ||
        appointment.version === null
    ) {
        throw new Error(
            "Appointment version is required."
        );
    }

    return request(
        `/appointments/${appointment.id}/cancel/`,
        {
            method: "POST",

            body: JSON.stringify({
                patient_id:
                    appointment.patient,

                expected_version:
                    appointment.version,
            }),
        }
    );
}


/* ============================================================
   APPOINTMENT HISTORY
============================================================ */

export async function getAppointmentHistory(
    id
) {

    if (!id) {
        throw new Error(
            "Appointment ID is required."
        );
    }

    return request(
        `/appointments/${id}/history/`
    );
}


/* ============================================================
   NOTIFICATIONS
============================================================ */

export async function getNotifications() {
    return request(
        "/notifications/"
    );
}


/* ============================================================
   DEFAULT EXPORT
============================================================ */

export default {
    getPatients,
    getProviders,

    getAppointments,
    getAppointment,
    createAppointment,

    confirmAppointment,
    rescheduleAppointment,
    cancelAppointment,

    getAppointmentHistory,
    getNotifications,
};
