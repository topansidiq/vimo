import "./config/runtime-paths.js";
import e from "express";
import { createServer } from "http";
import { Server } from "socket.io";
import { logger } from "./config/logger.js";
import { middleware } from "./middleware/index.js";
import deviceRoutes from "./routes/device.js";
import databaseSqlite from "./database/sqlite.js";
import { MQTT } from "./config/mqtt.js";

const app = e();
const httpServer = createServer(app);
const io = new Server(httpServer, {
    cors: {
        origin: "*",
    }
});

// MQTT Setup
let mqttManager;

try {
    mqttManager = new MQTT();
} catch (err) {
    console.error(`MQTT configuration error: ${err.message}`);
    process.exit(1);
}

const mqttClient = mqttManager.client();
const mqttInfo = mqttManager.info();
const mqttTopic = mqttManager.topic();
let mqttStatus = "connecting";

mqttClient.on('connect', () => {
    mqttStatus = "connected";
    console.info(`Connected to MQTT broker (${mqttInfo.provider}: ${mqttInfo.broker})`);
    mqttClient.subscribe(mqttTopic, (err) => {
        if (err) {
            console.error(`Failed to subscribe to ${mqttTopic}: ${err.message}`);
        } else {
            console.info(`Subscribed to ${mqttTopic}`);
        }
    });
});

mqttClient.on('reconnect', () => {
    mqttStatus = "reconnecting";
    console.warn('MQTT reconnecting...');
});

mqttClient.on('offline', () => {
    mqttStatus = "offline";
    console.warn('MQTT client offline');
});

mqttClient.on('close', () => {
    mqttStatus = "disconnected";
    console.warn('MQTT connection closed');
});

mqttClient.on('error', (err) => {
    mqttStatus = "error";
    console.error(`MQTT error: ${err.message}`);
});

mqttClient.on('message', (topic, message) => {
    try {
        const payload = JSON.parse(message.toString());
        // Use device_id from topic (vimo/devices/{device_id}/data) or fallback to ID in payload
        const parts = topic.split('/');
        const deviceId = (parts.length >= 3) ? parts[2] : (payload.id || payload.device_id || "UNKNOWN");

        // ESP32 sends { id: "...", data: { ax: ..., ay: ... } }
        // We normalize this to { accelX: ..., accelY: ... }
        const sensorData = payload.data || payload;

        const normalized = {
            accelX: sensorData.accelX ?? sensorData.ax,
            accelY: sensorData.accelY ?? sensorData.ay,
            accelZ: sensorData.accelZ ?? sensorData.az,
            gyroX: sensorData.gyroX ?? sensorData.gx,
            gyroY: sensorData.gyroY ?? sensorData.gy,
            gyroZ: sensorData.gyroZ ?? sensorData.gz
        };

        const data = {
            device_id: deviceId,
            data: normalized
        };

        io.emit('mpu_data', data);
    } catch (err) {
        console.error('Error parsing MQTT message:', err);
    }
});

// Socket.IO
io.on('connection', (socket) => {
    console.info(`Client connected: ${socket.id}`);
    socket.on('disconnect', () => {
        console.info(`Client disconnected: ${socket.id}`);
    });
});

// app.use(middleware.apiKey);
app.use(middleware.requestLogger(logger));
app.use(e.json());
app.use('/api/devices', deviceRoutes);

app.get('/health', (req, res) => {
    return res.json({ status: 'ok', service: 'vimo-server' });
});

app.get('/ready', (req, res) => {
    let databaseOk = false;
    try {
        databaseSqlite.prepare('SELECT 1 AS ok').get();
        databaseOk = true;
    } catch (err) {
        logger.warn('Readiness database check failed', { message: err.message });
    }
    const mqttReady = mqttStatus === 'connected';
    const ready = databaseOk && mqttReady;
    return res.status(ready ? 200 : 503).json({
        ready,
        database: databaseOk,
        mqtt: mqttStatus,
    });
});

app.get('/', (req, res) => {
    return res.json({
        status: 'ok',
        websocket: 'active',
        mqtt: mqttStatus,
        mqtt_provider: mqttInfo.provider,
        mqtt_broker: mqttInfo.broker,
        mqtt_topic: mqttTopic
    });
});

const parsedPort = Number.parseInt(process.env.APP_PORT || process.env.PORT || '3001', 10);
const appPort = Number.isInteger(parsedPort) && parsedPort > 0 ? parsedPort : 3001;

httpServer.listen(appPort, () => {
    console.info(`Server running on http://localhost:${appPort}`);
});

function shutdown() {
    databaseSqlite.close();
    mqttClient.end();
    console.info('Connections closed!');
    process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
