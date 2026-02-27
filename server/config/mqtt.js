import './runtime-paths.js';
import crypto from 'node:crypto';
import mqtt from 'mqtt';

const DEFAULT_LOCAL_BROKER = 'mqtt://localhost:1883';
const DEFAULT_TOPIC = 'vimo/devices/+/data';
const DEFAULT_HIVEMQ_PROTOCOL = 'mqtts';
const DEFAULT_HIVEMQ_PORT = 8883;

export class MQTT {
    #config = buildMqttConfig();

    client() {
        return mqtt.connect(this.#config.url, this.#config.options);
    }

    topic() {
        return getMqttTopic();
    }

    info() {
        return {
            provider: this.#config.provider,
            broker: this.#config.safeUrl,
            topic: getMqttTopic()
        };
    }
}

export function getMqttTopic() {
    return process.env.MQTT_TOPIC_SUBSCRIBE?.trim() || DEFAULT_TOPIC;
}

function buildMqttConfig() {
    const provider = resolveProvider();

    if (provider === 'local') {
        const url = process.env.MQTT_LOCAL_URL?.trim() || process.env.MQTT_BROKER?.trim() || DEFAULT_LOCAL_BROKER;

        return {
            provider: 'local',
            url,
            safeUrl: redactBrokerUrl(url),
            options: {}
        };
    }

    if (provider === 'hivemq') {
        const host = process.env.MQTT_HIVEMQ_HOST?.trim();
        const username = process.env.MQTT_HIVEMQ_USERNAME?.trim();
        const password = process.env.MQTT_HIVEMQ_PASSWORD;

        if (!host) {
            throw new Error('MQTT_HIVEMQ_HOST is required when MQTT_PROVIDER=hivemq');
        }

        if (!username || !password) {
            throw new Error('MQTT_HIVEMQ_USERNAME and MQTT_HIVEMQ_PASSWORD are required when MQTT_PROVIDER=hivemq');
        }

        const protocol = process.env.MQTT_HIVEMQ_PROTOCOL?.trim() || DEFAULT_HIVEMQ_PROTOCOL;
        const port = parsePositiveInt(process.env.MQTT_HIVEMQ_PORT, DEFAULT_HIVEMQ_PORT);
        const url = `${protocol}://${host}:${port}`;
        const clientId = process.env.MQTT_HIVEMQ_CLIENT_ID?.trim() || `vimo-server-${crypto.randomBytes(4).toString('hex')}`;

        return {
            provider: 'hivemq',
            url,
            safeUrl: redactBrokerUrl(url),
            options: {
                username,
                password,
                clientId,
                reconnectPeriod: parsePositiveInt(process.env.MQTT_RECONNECT_PERIOD_MS, 3000),
                connectTimeout: parsePositiveInt(process.env.MQTT_CONNECT_TIMEOUT_MS, 30000),
                rejectUnauthorized: toBoolean(process.env.MQTT_HIVEMQ_REJECT_UNAUTHORIZED, true)
            }
        };
    }

    throw new Error(`Unsupported MQTT_PROVIDER "${provider}". Use "local" or "hivemq".`);
}

function parsePositiveInt(value, fallback) {
    const parsed = Number.parseInt(value, 10);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function resolveProvider() {
    const provider = process.env.MQTT_PROVIDER?.trim().toLowerCase();

    if (provider === 'local' || provider === 'mosquitto') {
        return 'local';
    }

    if (provider === 'hivemq') {
        return 'hivemq';
    }

    if (provider && provider !== 'local' && provider !== 'hivemq' && provider !== 'mosquitto') {
        return provider;
    }

    if (process.env.MQTT_HIVEMQ_HOST || process.env.MQTT_HIVEMQ_USERNAME) {
        return 'hivemq';
    }

    return 'local';
}

function redactBrokerUrl(url) {
    try {
        const parsed = new URL(url);

        if (parsed.username || parsed.password) {
            parsed.username = '***';
            parsed.password = '***';
            return parsed.toString();
        }
    } catch {
        return url;
    }

    return url;
}

function toBoolean(value, fallback = true) {
    if (typeof value !== 'string') {
        return fallback;
    }

    const normalized = value.trim().toLowerCase();

    if (normalized === 'true') {
        return true;
    }

    if (normalized === 'false') {
        return false;
    }

    return fallback;
}
