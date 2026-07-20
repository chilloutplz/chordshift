<script setup>

import { ref } from "vue";
import { uploadImage } from "../api/chord";

const selectedFile = ref(null);
const preview = ref("");
const result = ref(null);

function onFileChange(event){

    const file = event.target.files[0];

    if(!file) return;

    selectedFile.value = file;

    preview.value = URL.createObjectURL(file);

}

async function upload(){

    if(!selectedFile.value) return;

    result.value = await uploadImage(selectedFile.value);

}

</script>

<template>

<div>

    <input
        type="file"
        accept="image/*"
        @change="onFileChange"
    >

    <br><br>

    <img
        v-if="preview"
        :src="preview"
        width="400"
    >

    <br><br>

    <button @click="upload">

        업로드

    </button>

    <pre v-if="result">

{{ result }}

    </pre>

</div>

</template>