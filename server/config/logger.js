import { appendFile, mkdir } from 'fs/promises';
import path from 'node:path';
import { runtimePaths } from './runtime-paths.js';

const LOG_DIR = runtimePaths.logDir;

// ANSI Colors
const colors = {
    reset: '\x1b[0m',
    info: '\x1b[36m',
    warn: '\x1b[33m',
    error: '\x1b[31m',
    debug: '\x1b[35m'
};

await mkdir(LOG_DIR, { recursive: true });

function getToday() {
    const now = new Date();
    return now.toISOString().split('T')[0]; // YYYY-MM-DD
}

function getLogFilePath() {
    return path.join(LOG_DIR, `app-${getToday()}.log`);
}

function formatMessage(level, message, meta) {
    const timestamp = new Date().toISOString();
    const metaString = meta ? ` ${JSON.stringify(meta)}` : '';
    return `[${timestamp}] [${level.toUpperCase()}] ${message}${metaString}`;
}

async function writeToFile(text) {
    const filePath = getLogFilePath();
    try {
        await appendFile(filePath, text + '\n', 'utf8');
    } catch (err) {
        console.error('Failed to write log file:', err.message);
    }
}

function log(level, message, meta) {
    const formatted = formatMessage(level, message, meta);

    // Colored console output
    console.log(`${colors[level]}${formatted}${colors.reset}`);

    // Daily file write
    writeToFile(formatted);
}

export const logger = {
    info(message, meta) {
        log('info', message, meta);
    },
    warn(message, meta) {
        log('warn', message, meta);
    },
    error(message, meta) {
        log('error', message, meta);
    },
    debug(message, meta) {
        log('debug', message, meta);
    }
};
