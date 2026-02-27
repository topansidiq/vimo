"""
Kalman Filter - 1D Linear Kalman Filter for IMU sensor noise reduction.

Digunakan untuk memperhalus (smooth) data raw dari sensor MPU6050.
Setiap axis (accelX/Y/Z, gyroX/Y/Z) memiliki instance filter sendiri.

Referensi:
  - Kalman, R.E. (1960). "A New Approach to Linear Filtering and Prediction Problems"
  - Maybeck, P.S. (1979). Stochastic Models, Estimation, and Control.

State model (constant-velocity 1D):
    x_k = [value, rate]  (position, velocity)
    z_k = [measured_value]
"""

import numpy as np


class KalmanFilter1D:
    """
    1D Linear Kalman Filter untuk satu axis sensor.

    Parameters
    ----------
    process_noise_q : float
        Process noise covariance (Q). Makin besar = lebih responsif terhadap
        perubahan, tapi lebih sedikit smoothing. Default 0.01.
    measurement_noise_r : float
        Measurement noise covariance (R). Representasi noise sensor.
        Makin besar = lebih percaya prediksi model daripada pengukuran.
        Untuk MPU6050: ~50-200 untuk accel, ~30-100 untuk gyro.
    initial_estimate_error : float
        Error estimasi awal (P). Default 1.0.
    """

    def __init__(
        self,
        process_noise_q: float = 0.01,
        measurement_noise_r: float = 100.0,
        initial_estimate_error: float = 1.0,
    ):
        # State estimate
        self._x: float = 0.0          # Estimated value
        self._p: float = initial_estimate_error  # Estimate error covariance

        # Noise parameters
        self._q: float = process_noise_q      # Process noise
        self._r: float = measurement_noise_r  # Measurement noise

        # Kalman Gain
        self._k: float = 0.0

        self._initialized: bool = False

    def update(self, measurement: float) -> float:
        """
        Proses satu pengukuran baru dan kembalikan nilai yang sudah difilter.

        Parameters
        ----------
        measurement : float
            Nilai raw dari sensor.

        Returns
        -------
        float
            Nilai estimasi setelah filter (smoothed).
        """
        if not self._initialized:
            # Inisialisasi dengan pengukuran pertama
            self._x = measurement
            self._initialized = True
            return self._x

        # ── Prediction Step ──────────────────────────────────────────────────
        # x_pred = x (model sederhana: nilai tidak berubah tanpa input)
        x_pred = self._x
        # p_pred = p + Q
        p_pred = self._p + self._q

        # ── Update Step ──────────────────────────────────────────────────────
        # Kalman Gain: K = P_pred / (P_pred + R)
        self._k = p_pred / (p_pred + self._r)

        # State update: x = x_pred + K * (z - x_pred)
        self._x = x_pred + self._k * (measurement - x_pred)

        # Covariance update: P = (1 - K) * P_pred
        self._p = (1.0 - self._k) * p_pred

        return self._x

    def reset(self):
        """Reset filter ke kondisi awal."""
        self._x = 0.0
        self._p = 1.0
        self._k = 0.0
        self._initialized = False

    @property
    def gain(self) -> float:
        """Kalman Gain saat ini (0-1). Mendekati 0 = lebih smooth."""
        return self._k

    @property
    def estimate(self) -> float:
        """Nilai estimasi terakhir."""
        return self._x


class IMUKalmanFilter:
    """
    Kalman Filter untuk seluruh data IMU (6-axis: Accel XYZ + Gyro XYZ).

    Setiap axis memiliki KalmanFilter1D sendiri agar tuning bisa dilakukan
    secara independen.
    """

    # Tuning default untuk MPU6050
    # Accel: noise lebih tinggi (getaran mekanik), gyro lebih stabil
    ACCEL_Q = 0.1     # Process noise accel
    ACCEL_R = 150.0   # Measurement noise accel (unit raw LSB)
    GYRO_Q  = 0.05    # Process noise gyro
    GYRO_R  = 80.0    # Measurement noise gyro (unit raw LSB)

    def __init__(self):
        self._filters = {
            "accel_x": KalmanFilter1D(self.ACCEL_Q, self.ACCEL_R),
            "accel_y": KalmanFilter1D(self.ACCEL_Q, self.ACCEL_R),
            "accel_z": KalmanFilter1D(self.ACCEL_Q, self.ACCEL_R),
            "gyro_x":  KalmanFilter1D(self.GYRO_Q,  self.GYRO_R),
            "gyro_y":  KalmanFilter1D(self.GYRO_Q,  self.GYRO_R),
            "gyro_z":  KalmanFilter1D(self.GYRO_Q,  self.GYRO_R),
        }

    def process(self, raw: dict) -> dict:
        """
        Proses satu set pengukuran raw IMU.

        Parameters
        ----------
        raw : dict
            {"accel_x": float, "accel_y": float, ..., "gyro_z": float}

        Returns
        -------
        dict
            Nilai yang sudah difilter dengan key yang sama.
        """
        return {
            axis: self._filters[axis].update(raw[axis])
            for axis in self._filters
        }

    def reset_all(self):
        """Reset semua filter."""
        for f in self._filters.values():
            f.reset()

    def tune(self, accel_q=None, accel_r=None, gyro_q=None, gyro_r=None):
        """
        Tuning ulang parameter noise filter saat runtime.

        q kecil  = lebih smooth, lambat merespons perubahan mendadak.
        q besar  = lebih responsif, kurang smooth.
        r kecil  = lebih percaya sensor (bisa lebih noisy).
        r besar  = lebih percaya model (lebih smooth).
        """
        for axis in ("accel_x", "accel_y", "accel_z"):
            f = self._filters[axis]
            if accel_q is not None:
                f._q = accel_q
            if accel_r is not None:
                f._r = accel_r

        for axis in ("gyro_x", "gyro_y", "gyro_z"):
            f = self._filters[axis]
            if gyro_q is not None:
                f._q = gyro_q
            if gyro_r is not None:
                f._r = gyro_r

    def get_gains(self) -> dict:
        """Kembalikan Kalman Gain tiap axis (untuk diagnostik)."""
        return {axis: f.gain for axis, f in self._filters.items()}
