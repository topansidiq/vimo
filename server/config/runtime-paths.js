import dotenv from 'dotenv';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const thisFile = fileURLToPath(import.meta.url);
const thisDir = path.dirname(thisFile);
const serverRoot = path.resolve(thisDir, '..');
const defaultAppRoot = path.resolve(serverRoot, '..');
const configuredRoot = process.env.VIMO_ROOT?.trim();
const appRoot = path.resolve(configuredRoot || defaultAppRoot);
const envPath = path.join(appRoot, '.env');

dotenv.config({ path: envPath, quiet: true });

export const runtimePaths = Object.freeze({
    serverRoot,
    appRoot,
    envPath,
    storageDir: path.join(appRoot, 'storage'),
    logDir: path.join(appRoot, 'storage', 'logs'),
    dbDir: path.join(appRoot, 'storage', 'private'),
    dbPath: path.join(appRoot, 'storage', 'private', 'app.db')
});
