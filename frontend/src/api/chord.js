import api from "./api";

export async function uploadImage(file) {

    const formData = new FormData();

    formData.append("image", file);

    const response = await api.post(
        "/chord/upload/",
        formData
    );

    return response.data;
}