from twin.ml import MLPredictor
from twin.schemas import MLPrediction


class ModelPredictor(MLPredictor):

    def predict(
        self,
        telemetry_window: list[dict],
    ) -> MLPrediction:

        return MLPrediction(
            anomaly_score=0.0,
            fault=None,
            confidence=0.0,
            rul_hours=None,
        )