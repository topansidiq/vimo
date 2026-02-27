import { Devices } from "../models/Devices.js";

export class DeviceService {
    static getAll() {
        return Devices.findAll();
    }
    static getById(id) {
        return Devices.findById(id);
    }

    // create a new device or update existing one based on provided id
    static async createOrUpdate(data) {
        if (!data.id) {
            throw new Error('Device id is required');
        }
        const existing = Devices.findById(data.id);
        if (existing) {
            // merge fields and update
            await Devices.update(data.id, data);
            return Devices.findById(data.id);
        } else {
            await Devices.create(data);
            return Devices.findById(data.id);
        }
    }

    static createDevice(data) {
        return Devices.create(data);
    }
    static updateDevice(id, data) {
        return Devices.update(id, data);
    }
    static truncateDevices() {
        return Devices.truncate();
    }
}