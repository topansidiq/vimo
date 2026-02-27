export class Validation {
    static _sanitizeData(data, allowed) {
        const safeData = {};
        for (const key of Object.keys(data)) {
            if (allowed.includes(key)) {
                safeData[key] = data[key];
            }
        }
        return safeData;
    }
}