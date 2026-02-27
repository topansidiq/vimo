import { Response } from "../../../lib/http/Response.js";
import { DeviceService } from "../../services/DeviceService.js";

export class DeviceController {
    static async index(req, res) {
        const devices = DeviceService.getAll();

        if (devices.length === 0) return Response.notFound(res);

        return Response.ok(res, devices);
    }
    static async show(req, res) {
        const { id } = req.params;
        const device = DeviceService.getById(id);

        if (!device) return Response.notFound(res);

        return Response.ok(res, device);
    }
    static async store(req, res) {
        const data = req.body;
        console.info('incoming device payload', data);
        try {
            const result = await DeviceService.createOrUpdate(data);
            return Response.ok(res, result, existing ? 200 : 201);
        } catch (err) {
            console.error(err);
            return Response.notFound(res);
        }
    }
    static async update(req, res) {
        const { id } = req.params;
        const data = req.body;
        const result = DeviceService.updateDevice(id, data);
        if (!result) return Response.notFound(res);
        return Response.ok(res, result, 201);
    }
    static async drop(req, res) {
        const result = DeviceService.truncateDevices();
        if (!result) return Response.notFound(res);
        return Response.okNoDataReturn(res);
    }
}
