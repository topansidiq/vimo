import e from "express";
import { DeviceController } from "../app/controllers/Resources/DeviceController.js";
import { catchAsync } from "../lib/utils/catchAsync.js";

const deviceRoutes = e.Router();

deviceRoutes.get('/', (req, res) => catchAsync(DeviceController.index(req, res)));
deviceRoutes.get('/:id', (req, res) => catchAsync(DeviceController.show(req, res)));
deviceRoutes.post('/', (req, res) => catchAsync(DeviceController.store(req, res)));
deviceRoutes.put('/:id', (req, res) => catchAsync(DeviceController.update(req, res)));
deviceRoutes.delete('/', (req, res) => catchAsync(DeviceController.drop(req, res)));

export default deviceRoutes;
