import { logger } from "../config/logger.js";

export const middleware = {
    apiKey: (req, res, next) => {
        const apiKey = req.header('x-api-key');

        if (!apiKey || apiKey !== process.env.API_KEY) {
            const start = process.hrtime.bigint();

            // Ambil IP asli (support reverse proxy)
            const userIp =
                req.headers['x-forwarded-for']?.split(',')[0] ||
                req.socket?.remoteAddress ||
                req.ip;

            const end = process.hrtime.bigint();
            const durationMs = Number(end - start) / 1_000_000;
            logger.warn(`${req.method} ${req.originalUrl} - ${res.statusCode} - ${durationMs.toFixed(
                2
            )}ms - ${userIp}`);
            return res.status(403).json({
                error: 'Unauthorized'
            });
        }

        next();
    },
    requestLogger: (logger) => {
        return (req, res, next) => {
            const start = process.hrtime.bigint();

            // Ambil IP asli (support reverse proxy)
            const userIp =
                req.headers['x-forwarded-for']?.split(',')[0] ||
                req.socket?.remoteAddress ||
                req.ip;

            // Log ketika response selesai
            res.on('finish', () => {
                const end = process.hrtime.bigint();
                const durationMs = Number(end - start) / 1_000_000;

                logger.info(
                    `${req.method} ${req.originalUrl} - ${res.statusCode} - ${durationMs.toFixed(
                        2
                    )}ms - ${userIp}`
                );
            });

            next();
        };
    },

    globalErrorHandler: (err, req, res, next) => {
        err.statusCode = err.statusCode || 500;
        err.status = err.status || 'ERROR';

        res.status(err.statusCode).json({
            status: err.status,
            message: err.message,
            stack: process.env.NODE_ENV === 'development' ? err.stack : undefined
        });
    }
};
