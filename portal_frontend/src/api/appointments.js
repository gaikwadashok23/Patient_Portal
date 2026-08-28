/*
 * Single source of truth:
 * appointment API operations live in api.js
 */

export {
    getAppointments,
    getAppointment,
    createAppointment,
    confirmAppointment,
    rescheduleAppointment,
    cancelAppointment,
    getAppointmentHistory,
    getNotifications,
} from "./api";