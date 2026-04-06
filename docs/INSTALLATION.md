# Instalasi & verifikasi Vimo (ringkas)

Panduan ini merangkum alur onboarding untuk tim deployment tanpa mengulang detail yang sudah ada di [README.md](../README.md) dan [server/README.md](../server/README.md).

## 1. Prasyarat

- Node.js LTS untuk `server/`.
- Python 3.9+ untuk desktop `vimo/` (dari source).
- Broker MQTT jika perangkat atau gateway memakai MQTT (Mosquitto lokal atau cloud).

## 2. Server (gateway + API)

1. Generate environment (Windows atau Linux) menggunakan skrip di `server/` (`npm run setup:windows`, `npm run setup:linux`, atau `npm run setup:env`).
2. Jalankan: `cd server && npm run start`.
3. Port HTTP mengikuti `APP_PORT` / `PORT` di root `.env` (default **3001**).
4. Verifikasi cepat:
   - `GET /health` — liveness.
   - `GET /ready` — siap menerima lalu lintas penuh (DB + MQTT terhubung).
   - `GET /` — ringkasan status MQTT.

## 3. Desktop

1. Di **Settings**, set **Bridge Server Host** dan **Port** agar mengarah ke API server (bukan broker MQTT).
2. Pilih **transport data**:
   - **WebSocket (Socket.IO)** — default; streaming real-time melalui server.
   - **MQTT** — subscribe langsung ke broker; tetap memakai HTTP untuk sinkron daftar perangkat.
   - **HTTP** — hanya polling daftar perangkat; **tanpa** streaming sensor live.
   - **Modbus TCP** — dicadangkan untuk iterasi berikutnya.

3. Simpan lalu **Connect to Server**.

## 4. Troubleshooting singkat

| Gejala | Tindakan |
|--------|----------|
| `/ready` mengembalikan 503 | Periksa koneksi MQTT di `.env` dan apakah broker berjalan. |
| Desktop tidak dapat fetch perangkat | Pastikan URL mengarah ke port API (`APP_PORT`), bukan port MQTT. |
| Mode MQTT tanpa data | Samakan **subscribe pattern** dengan topik perangkat (default server: `vimo/devices/+/data`). |

## 5. Dokumen terkait

- [../README.md](../README.md) — quick start, build installer, struktur repo.
- [../server/README.md](../server/README.md) — detail MQTT dan setup env.
- [../issue.md](../issue.md) — arah pengembangan v2.
