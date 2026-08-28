import apiClient from "./client";


export const getProviders = async () => {

    const response =
        await apiClient.get("/providers/");

    return response.data;
};