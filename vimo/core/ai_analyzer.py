"""
Lightweight AI Anomaly Detection model using Online Z-Score and Exponential Moving Average.
Used to differentiate real alert spikes from minor sensor noise.
"""
import math
from collections import deque


class VimoAIAnalyzer:
    """
    Lightweight Statistical AI for real-time anomaly detection.
    Maintains a running mean and variance to calculate Z-scores dynamically.
    """
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self._accel_history = deque(maxlen=window_size)
        self._gyro_history = deque(maxlen=window_size)
        
        # Exponential Moving Average for smoothing
        self.alpha = 0.1
        self.ema_accel = None
        self.ema_gyro = None

    def analyze(self, accel_mag: float, gyro_mag: float, sensitivity: float = 3.0) -> dict:
        """
        Analyze current readings and return a dict of analysis results.
        :param accel_mag: Current acceleration magnitude
        :param gyro_mag: Current gyroscope magnitude
        :param sensitivity: Z-score threshold for anomaly (e.g., 3.0 means 3 std devs)
        :return: {"is_anomaly": bool, "accel_z": float, "gyro_z": float, "message": str}
        """
        # 1. Update Exponential Moving Averages
        if self.ema_accel is None:
            self.ema_accel = accel_mag
            self.ema_gyro = gyro_mag
        else:
            self.ema_accel = (self.alpha * accel_mag) + ((1 - self.alpha) * self.ema_accel)
            self.ema_gyro = (self.alpha * gyro_mag) + ((1 - self.alpha) * self.ema_gyro)

        # 2. Add raw to history
        self._accel_history.append(accel_mag)
        self._gyro_history.append(gyro_mag)

        # 3. Need enough data points to establish a baseline
        if len(self._accel_history) < 20:
            return {"is_anomaly": False, "accel_z": 0.0, "gyro_z": 0.0, "message": "Calibrating AI..."}

        # 4. Calculate Mean and Std Deviation
        mean_a = sum(self._accel_history) / len(self._accel_history)
        var_a = sum((x - mean_a) ** 2 for x in self._accel_history) / len(self._accel_history)
        std_a = math.sqrt(var_a) if var_a > 0 else 0.001

        mean_g = sum(self._gyro_history) / len(self._gyro_history)
        var_g = sum((x - mean_g) ** 2 for x in self._gyro_history) / len(self._gyro_history)
        std_g = math.sqrt(var_g) if var_g > 0 else 0.001

        # 5. Calculate Z-Scores
        z_score_a = abs(accel_mag - mean_a) / std_a
        z_score_g = abs(gyro_mag - mean_g) / std_g

        # 6. Evaluate Anomaly thresholds
        is_anomaly = False
        msgs = []
        if z_score_a > sensitivity:
            is_anomaly = True
            msgs.append(f"Accel Spike (Z: {z_score_a:.1f})")
        if z_score_g > sensitivity:
            is_anomaly = True
            msgs.append(f"Gyro Spike (Z: {z_score_g:.1f})")

        return {
            "is_anomaly": is_anomaly,
            "accel_z": z_score_a,
            "gyro_z": z_score_g,
            "message": " & ".join(msgs) if is_anomaly else "Normal",
            "ema_accel": self.ema_accel,
            "ema_gyro": self.ema_gyro
        }
