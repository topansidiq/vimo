// import mqtt from 'mqtt';

// const broker = 'mqtt://localhost:1883';
// const client = mqtt.connect(broker);

// const deviceId = 'DEV-999';
// const topic = `vimo/devices/${deviceId}/data`;

// client.on('connect', () => {
//     console.log(`Connected to broker at ${broker}`);
//     console.log(`Simulating device ${deviceId} on topic ${topic}`);

//     setInterval(() => {
//         const payload = {
//             accelX: Math.floor(Math.random() * 2000 - 1000),
//             accelY: Math.floor(Math.random() * 2000 - 1000),
//             accelZ: Math.floor(Math.random() * 16000),
//             gyroX: Math.floor(Math.random() * 400 - 200),
//             gyroY: Math.floor(Math.random() * 400 - 200),
//             gyroZ: Math.floor(Math.random() * 400 - 200)
//         };

//         client.publish(topic, JSON.stringify(payload));
//         console.log(`Published to ${topic}: ${JSON.stringify(payload)}`);
//     }, 50);
// });

// client.on('error', (err) => {
//     console.error('MQTT Error:', err);
// });

import { MQTT } from './config/mqtt.js';

let mqttManager;

try {
    mqttManager = new MQTT();
} catch (err) {
    console.error(`MQTT configuration error: ${err.message}`);
    process.exit(1);
}

const client = mqttManager.client();
const mqttInfo = mqttManager.info();

const devices = [
    'DEV-999',
    'DEV-888',
    'DEV-777'
];

client.on('connect', () => {
    console.log(`Connected to broker at ${mqttInfo.broker}`);
    console.log(`Simulating ${devices.length} devices...`);

    devices.forEach((deviceId) => {

        const topic = `vimo/devices/${deviceId}/data`;

        setInterval(() => {
            const payload = {
                deviceId,
                timestamp: Date.now(),
                accelX: Math.floor(Math.random() * 2000 - 1000),
                accelY: Math.floor(Math.random() * 2000 - 1000),
                accelZ: Math.floor(Math.random() * 16000),
                gyroX: Math.floor(Math.random() * 400 - 200),
                gyroY: Math.floor(Math.random() * 400 - 200),
                gyroZ: Math.floor(Math.random() * 400 - 200)
            };

            client.publish(topic, JSON.stringify(payload), { qos: 0 });
            // console.log(`Published to ${topic}`);
        }, 50);

    });
});

client.on('error', (err) => {
    console.error('MQTT Error:', err);
});
