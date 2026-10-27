# Continue Development mode for version 2 Vimo

## Ringkasan

Issue ini mencakup arah pengembangan Vimo versi 2: mempermudah adopsi melalui instalasi dan operasi server yang lebih ramping, memberi fleksibilitas komunikasi perangkat melalui beberapa protokol industri, serta memperluas nilai produk dengan kemampuan prediksi dan alur pemeliharaan.

## Tujuan

- Mengurangi waktu dan risiko kesalahan saat pertama kali men-deploy Vimo di lingkungan pelanggan.
- Membuat konfigurasi saluran data (transport) dapat dipilih dan diubah sesuai kebutuhan integrasi tanpa mengunci ke satu protokol saja.
- Menyediakan fondasi fitur operasional untuk perawatan preventif berbasis data historis dan sinyal operasi.

---

## 1. Penyederhanaan instalasi dan setup server

**Masalah yang dituju:** Proses instalasi dan konfigurasi server (gateway MQTT dan layanan manajemen perangkat) saat ini berpotensi memakan banyak langkah manual atau pengetahuan infrastruktur.

**Arah kerja:**

- Mendefinisikan alur instalasi yang jelas end-to-end: dari prasyarat lingkungan hingga verifikasi bahwa layanan berjalan dan dapat diakses oleh aplikasi desktop / klien lain.
- Menyatukan atau mendokumentasikan dependensi (runtime, port, kredensial default vs produksi) agar tim operasi atau pelanggan tidak perlu menebak.
- Mempertimbangkan opsi distribusi yang mengurangi langkah manual (misalnya bundel konfigurasi, skrip bootstrap, atau panduan terstruktur).
- Menyediakan titik pemeriksaan (health / readiness) agar setelah instalasi mudah memastikan bahwa gateway dan microservice berfungsi.

**Hasil yang diharapkan:** Waktu onboarding lebih pendek, lebih sedikit tiket dukungan terkait “server tidak jalan” atau konfigurasi salah, dan dokumentasi yang dapat diikuti oleh peran non-pengembang inti.

---

## 2. Dukungan pergantian / pemilihan protokol

**Masalah yang dituju:** Integrasi perangkat dan sistem pihak ketiga membutuhkan fleksibilitas transport: tidak semua lingkungan memakai pola yang sama.

**Cakupan protokol (referensi):** HTTP, MQTT, WebSocket, dan Modbus.

**Arah kerja:**

- Menambahkan bagian konfigurasi atau pengaturan produk yang memungkinkan pemilihan atau pergantian mode komunikasi yang relevan untuk use case Vimo, dengan penjelasan singkat kapan memakai masing-masing opsi.
- Memastikan perilaku yang konsisten di lapisan aplikasi (autentikasi, alamat endpoint, format pesan di tingkat konsep) meskipun transport berbeda.
- Mengantisipasi migrasi: dari setup lama ke protokol baru tanpa kehilangan visibilitas perangkat atau data kritis.
- Keamanan dan operasional: TLS di mana relevan, pembatasan akses, dan logging yang cukup untuk troubleshooting tanpa mengekspos data sensitif.

**Hasil yang diharapkan:** Tim integrasi dapat menyesuaikan Vimo dengan arsitektur pelanggan (cloud, on-prem, SCADA/PLC) dengan risiko regresi yang terkelola.

---

## 3. Fitur baru: prediksi pemeliharaan dan proses pemeliharaan

**Masalah yang dituju:** Operator membutuhkan lebih dari monitoring real-time: indikasi awal kerusakan atau degradasi, dan alur kerja yang mendukung perencanaan perbaikan.

**Arah kerja:**

- **Prediksi pemeliharaan (maintenance prediction):** Menggabungkan data operasi menjadi sinyal atau rekomendasi prioritas dengan transparansi dasar mengapa suatu aset ditandai.
- **Proses pemeliharaan (maintenance process):** Mendukung siklus kerja dari deteksi hingga tindakan: penjadwalan, penugasan, status pekerjaan, dan penutupan kasus.

**Hasil yang diharapkan:** Pengurangan downtime tidak terencana, perencanaan suku cadang dan tenaga lebih baik, dan jejak audit untuk keputusan pemeliharaan.

---

## Ruang lingkup dan asumsi

- Versi 2 membangun di atas arsitektur yang ada (server gateway + microservice manajemen perangkat + aplikasi desktop); perubahan besar arsitektur, jika ada, akan didiskusikan terpisah.
- Detail implementasi (pustaka, skema database, endpoint API) akan dirinci pada tiket turunan atau dokumen teknis setelah prioritas fitur disepakati.

## Kriteria sukses (tingkat tinggi)

- Dokumen atau pengalaman instalasi yang dapat diikuti oleh peran deployment tanpa bimbingan intensif dari tim inti.
- Setidaknya satu jalur teruji untuk masing-masing protokol yang disebutkan, dengan panduan konfigurasi yang konsisten.
- Alur prediksi dan proses pemeliharaan dapat didemonstrasikan end-to-end pada skenario referensi (contoh aset / dataset internal).
