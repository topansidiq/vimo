import database from "../../database/sqlite.js";
import { Validation } from "../../lib/helpers/Validation.js";

export class Devices {
    static tableName = 'devices';

    static allowedColumns = ['id', 'name', 'location', 'status'];

    static allowedStatus = ['idle', 'off', 'error', 'maintenance'];

    static findAll() {
        return database.prepare(`SELECT * FROM ${this.tableName} WHERE deleted_at IS NULL`).all();
    }

    static findById(id) {
        return database.prepare(`SELECT * FROM ${this.tableName} WHERE id = ? AND deleted_at IS NULL`).get(id);
    }

    static create(data) {
        if (data.status && !this.allowedStatus.includes(data.status)) {
            throw new Error(`Status tidak valid. Pilih: ${this.allowedStatus.join(', ')}`);
        }

        const safeData = Validation._sanitizeData(data, this.allowedColumns);
        if (Object.keys(safeData).length === 0) throw new Error("Data tidak valid.");

        // Use provided id from ESP or generate new UUID if not provided
        if (!safeData.id) safeData.id = crypto.randomUUID();

        const columns = Object.keys(safeData).join(', ');
        const values = Object.keys(safeData).map(key => `@${key}`).join(', ');

        return database.prepare(`INSERT INTO ${this.tableName} (${columns}) VALUES (${values})`).run(safeData);
    }

    static update(id, data) {
        if (data.status && !this.allowedStatus.includes(data.status)) {
            throw new Error("Nilai status tidak diizinkan.");
        }

        const safeData = Validation._sanitizeData(data, this.allowedColumns);

        if (Object.keys(safeData).length === 0) throw new Error("Tidak ada field valid untuk diupdate.");

        const setQuery = Object.keys(safeData).map(key => `${key} = @${key}`).join(', ');
        const stmt = database.prepare(`UPDATE ${this.tableName} SET ${setQuery} WHERE id = @id AND deleted_at IS NULL`);

        return stmt.run({ ...safeData, id });
    }

    static softDelete(id) {
        const stmt = database.prepare(`UPDATE ${this.tableName} SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?`);
        return stmt.run(id);
    }

    static delete(id) {
        const stmt = database.prepare(`DELETE FROM ${this.tableName} WHERE id = ?`);
        return stmt.run(id);
    }

    static truncate() {
        return database.prepare(`DELETE FROM ${this.tableName}`).run();
    }
}