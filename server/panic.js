import { MQTT } from "./config/mqtt.js";

const topic = "vimo/panic";
const payload = "panic";

let mqttManager;

try {
  mqttManager = new MQTT();
} catch (err) {
  console.error(`MQTT configuration error: ${err.message}`);
  process.exit(1);
}

const client = mqttManager.client();
const mqttInfo = mqttManager.info();

client.on("connect", () => {
  console.log(`Connected to ${mqttInfo.provider} broker (${mqttInfo.broker})`);
  client.publish(topic, payload, { qos: 1, retain: false }, (err) => {
    if (err) {
      console.error("Publish error:", err.message);
      client.end(true);
      process.exitCode = 1;
      return;
    }

    console.log(`Published "${payload}" to "${topic}"`);
    client.end();
  });
});

client.on("error", (err) => {
  console.error("MQTT connection error:", err.message);
  client.end(true);
  process.exitCode = 1;
});
