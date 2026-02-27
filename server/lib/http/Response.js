export class Response {
    static ok(res, dta = [], code = 200) {
        return res.status(code).json({
            status: 'OK',
            data: dta
        });
    }

    static okNoDataReturn(res, code = 200) {
        return res.status(code).json({
            status: 'OK',
        });
    }

    static notFound(res, msg = 'Nothing data found!') {
        return res.status(404).json({
            status: 'NOT_FOUND',
            message: msg
        });
    }

    static error(res, msg = 'Internal Server Error', code = 500) {
        return res.status(code).json({
            status: 'ERROR',
            message: msg
        });
    }
}