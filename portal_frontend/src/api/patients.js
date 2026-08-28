import apiClient from "./client";


export const getPatients = async () => {

    const response =
        await apiClient.get("/patients/");

    return response.data;
};